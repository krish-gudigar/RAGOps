"""Application settings.

Model names and prices are CONFIGURABLE DEMO VALUES. The prices below are
placeholders, not real provider prices. Costs shown in the app are
ESTIMATES based on these numbers.
"""

import os
import copy
from dataclasses import dataclass, field
from enum import Enum

from pathlib import Path
from dotenv import load_dotenv

# Look for .env in project root or current working dir
_root_env = Path(__file__).resolve().parent.parent.parent / ".env"
if _root_env.exists():
    load_dotenv(_root_env)
else:
    load_dotenv()

TIERS = ("small", "medium", "strong")  # order matters: weakest to strongest


class Expert(str, Enum):
    GENERAL = "general"
    CODING = "coding"
    REASONING = "reasoning"


TASK_TYPE_TO_EXPERT: dict[str, Expert] = {
    "debugging": Expert.CODING,
    "coding": Expert.CODING,
    "mathematics": Expert.REASONING,
    "reasoning": Expert.REASONING,
    "planning": Expert.REASONING,
    "summarization": Expert.GENERAL,
    "extraction": Expert.GENERAL,
    "structured_output": Expert.GENERAL,
    "transformation": Expert.GENERAL,
    "general_question": Expert.GENERAL,
    "unknown": Expert.GENERAL,
}


@dataclass
class Thresholds:
    # total_score <= low_max     -> "low"
    # total_score <= medium_max  -> "medium"
    # anything higher            -> "high"
    low_max: int = 3
    medium_max: int = 7

    # Estimated input tokens that raise the context score
    medium_context_tokens: int = 200   # at or above -> context score 1
    long_context_tokens: int = 1000    # at or above -> context score 2


@dataclass
class ModelConfig:
    name: str
    price_in_per_1m: float      # estimated price per 1M input tokens
    price_out_per_1m: float     # estimated price per 1M output tokens
    expected_latency_ms: int    # rough expectation, used for display only


def _default_models() -> dict[str, ModelConfig]:
    # `or` also handles an empty value like SMALL_MODEL= in a .env file
    return {
        "small": ModelConfig(os.getenv("SMALL_MODEL") or "small-demo", 0.10, 0.40, 400),
        "medium": ModelConfig(os.getenv("MEDIUM_MODEL") or "medium-demo", 0.50, 1.50, 1200),
        "strong": ModelConfig(os.getenv("STRONG_MODEL") or "strong-demo", 3.00, 15.00, 3000),
    }


def _default_expert_models(models: dict[str, ModelConfig]) -> dict[Expert, dict[str, str | None]]:
    return {
        Expert.GENERAL: {tier: model.name for tier, model in models.items()},
        Expert.CODING: {
            "small": os.getenv("CODING_SMALL_MODEL") or "qwen2.5-coder:0.5b",
            "medium": os.getenv("CODING_MEDIUM_MODEL") or "qwen2.5-coder:1.5b",
            "strong": os.getenv("CODING_STRONG_MODEL") or "qwen2.5-coder:3b",
        },
        # Example: map these to locally verified reasoning-capable model tags.
        Expert.REASONING: {"small": None, "medium": None, "strong": None},
    }


EXPERT_MODELS: dict[Expert, dict[str, str | None]] = _default_expert_models(_default_models())


@dataclass
class Settings:
    thresholds: Thresholds = field(default_factory=Thresholds)
    models: dict[str, ModelConfig] = field(default_factory=_default_models)
    expert_models: dict[Expert, dict[str, str | None]] = field(
        default_factory=lambda: copy.deepcopy(EXPERT_MODELS)
    )
    expert_model_prices: dict[str, ModelConfig] = field(default_factory=dict)

    # Expert routing is opt-in. Embedding settings are placeholders to tune with
    # scripts/inspect_gate.py after reviewing the local example bank.
    use_experts: bool = False
    embedding_model: str = "all-minilm"
    embedding_top_k: int = 3
    embedding_min_score: float = 0.45
    embedding_min_margin: float = 0.05
    embedding_timeout_s: float = 15.0

    # Output length is unknown before running, so cost estimates assume this.
    assumed_output_tokens: int = 200

    # Safety rule: tasks with reliability score 2 never go to the small tier.
    raise_small_for_high_reliability: bool = True

    def __post_init__(self) -> None:
        if not self.expert_models:
            self.expert_models = _default_expert_models(self.models)
        self.expert_models[Expert.GENERAL] = {
            tier: model.name for tier, model in self.models.items()
        }
        self.ensure_expert_model_prices()

    def ensure_expert_model_prices(self) -> None:
        for expert, tier_models in self.expert_models.items():
            if expert == Expert.GENERAL:
                continue
            for tier, name in tier_models.items():
                if name and name not in self.expert_model_prices:
                    base = self.models[tier]
                    self.expert_model_prices[name] = ModelConfig(
                        name=name,
                        price_in_per_1m=base.price_in_per_1m,
                        price_out_per_1m=base.price_out_per_1m,
                        expected_latency_ms=base.expected_latency_ms,
                    )

    def model_for(self, tier: str, expert: Expert = Expert.GENERAL) -> ModelConfig:
        if expert == Expert.GENERAL:
            return self.models[tier]
        name = self.expert_models.get(expert, {}).get(tier)
        if not name:
            return self.models[tier]
        price = self.expert_model_prices.get(name)
        if price:
            return price
        base = self.models[tier]
        return ModelConfig(
            name=name,
            price_in_per_1m=base.price_in_per_1m,
            price_out_per_1m=base.price_out_per_1m,
            expected_latency_ms=base.expected_latency_ms,
        )

    def estimate_cost(
        self, tier: str, input_tokens: int, output_tokens: int,
        expert: Expert = Expert.GENERAL,
    ) -> float:
        m = self.model_for(tier, expert)
        return (input_tokens * m.price_in_per_1m + output_tokens * m.price_out_per_1m) / 1_000_000