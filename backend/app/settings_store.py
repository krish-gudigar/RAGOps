"""Change settings while the app runs, and remember them in a small JSON file.

Settings objects are updated IN PLACE, so everything that already holds a
reference (the analyzer, routers, providers) sees the new values immediately.
Model NAMES are not editable here; they come from .env.
"""

import copy
import dataclasses
import json
import logging
from pathlib import Path

from app.config import Settings, Thresholds
from app.models.api_models import (
    ModelSettings, SettingsSnapshot, SettingsUpdate, ThresholdValues,
)

log = logging.getLogger("routewise.settings")


class SettingsStore:
    def __init__(self, settings: Settings, path: str | Path | None = "data/settings.json"):
        self.settings = settings
        self.path = Path(path) if path else None
        self._defaults = copy.deepcopy(settings)
        self._load()

    # ---------- read ----------
    def snapshot(self) -> SettingsSnapshot:
        s = self.settings
        return SettingsSnapshot(
            thresholds=ThresholdValues(**dataclasses.asdict(s.thresholds)),
            raise_small_for_high_reliability=s.raise_small_for_high_reliability,
            assumed_output_tokens=s.assumed_output_tokens,
            use_experts=s.use_experts,
            embedding_model=s.embedding_model,
            embedding_top_k=s.embedding_top_k,
            embedding_min_score=s.embedding_min_score,
            embedding_min_margin=s.embedding_min_margin,
            embedding_timeout_s=s.embedding_timeout_s,
            models={tier: ModelSettings(**dataclasses.asdict(m)) for tier, m in s.models.items()},
            expert_models=copy.deepcopy(s.expert_models),
            expert_model_prices={
                name: ModelSettings(**dataclasses.asdict(model))
                for name, model in s.expert_model_prices.items()
            },
        )

    # ---------- change ----------
    def apply(self, update: SettingsUpdate) -> SettingsSnapshot:
        """Raises ValueError if the combined values make no sense. Nothing changes in that case."""
        self._apply(update)
        self._save()
        return self.snapshot()

    def reset(self) -> SettingsSnapshot:
        d, s = self._defaults, self.settings
        for f in dataclasses.fields(Thresholds):
            setattr(s.thresholds, f.name, getattr(d.thresholds, f.name))
        s.raise_small_for_high_reliability = d.raise_small_for_high_reliability
        s.assumed_output_tokens = d.assumed_output_tokens
        s.use_experts = d.use_experts
        s.embedding_model = d.embedding_model
        s.embedding_top_k = d.embedding_top_k
        s.embedding_min_score = d.embedding_min_score
        s.embedding_min_margin = d.embedding_min_margin
        s.embedding_timeout_s = d.embedding_timeout_s
        s.expert_models = copy.deepcopy(d.expert_models)
        s.expert_model_prices = copy.deepcopy(d.expert_model_prices)
        for tier, model in s.models.items():
            for field in ("price_in_per_1m", "price_out_per_1m", "expected_latency_ms"):
                setattr(model, field, getattr(d.models[tier], field))
        if self.path and self.path.exists():
            self.path.unlink()
        return self.snapshot()

    # ---------- internals ----------
    def _apply(self, update: SettingsUpdate) -> None:
        s = self.settings
        thresholds = dataclasses.asdict(s.thresholds)
        if update.thresholds:
            thresholds.update(update.thresholds.model_dump(exclude_none=True))
        if thresholds["low_max"] >= thresholds["medium_max"]:
            raise ValueError("low_max must be smaller than medium_max.")
        if thresholds["medium_context_tokens"] >= thresholds["long_context_tokens"]:
            raise ValueError("medium_context_tokens must be smaller than long_context_tokens.")

        for name, value in thresholds.items():
            setattr(s.thresholds, name, value)
        if update.raise_small_for_high_reliability is not None:
            s.raise_small_for_high_reliability = update.raise_small_for_high_reliability
        if update.assumed_output_tokens is not None:
            s.assumed_output_tokens = update.assumed_output_tokens
        for name in (
            "use_experts", "embedding_model", "embedding_top_k",
            "embedding_min_score", "embedding_min_margin", "embedding_timeout_s",
        ):
            value = getattr(update, name)
            if value is not None:
                setattr(s, name, value)
        if update.expert_models:
            for expert, tier_models in update.expert_models.items():
                s.expert_models[expert].update(tier_models)
            s.ensure_expert_model_prices()
        for tier, model_update in (update.models or {}).items():
            for field, value in model_update.model_dump(exclude_none=True).items():
                setattr(s.models[tier], field, value)
        for name, model_update in (update.expert_model_prices or {}).items():
            if name not in s.expert_model_prices:
                raise ValueError(f"Unknown expert model price entry '{name}'.")
            for field, value in model_update.model_dump(exclude_none=True).items():
                setattr(s.expert_model_prices[name], field, value)

    def _save(self) -> None:
        if not self.path:
            return
        snap = self.snapshot().model_dump()
        for model in snap["models"].values():
            model.pop("name")          # names come from .env, not from this file
        for model in snap["expert_model_prices"].values():
            model.pop("name")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(snap, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            self._apply(SettingsUpdate.model_validate_json(self.path.read_text(encoding="utf-8")))
        except (ValueError, OSError) as error:
            log.warning("Ignoring unreadable settings file %s: %s", self.path, error)