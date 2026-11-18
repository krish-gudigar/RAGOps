"""Application settings.

Model names and prices are CONFIGURABLE DEMO VALUES. The prices below are
placeholders, not real provider prices. Costs shown in the app are
ESTIMATES based on these numbers.
"""

import os
from dataclasses import dataclass, field

from pathlib import Path
from dotenv import load_dotenv

# Look for .env in project root or current working dir
_root_env = Path(__file__).resolve().parent.parent.parent / ".env"
if _root_env.exists():
    load_dotenv(_root_env)
else:
    load_dotenv()

TIERS = ("small", "medium", "strong")  # order matters: weakest to strongest


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


@dataclass
class Settings:
    thresholds: Thresholds = field(default_factory=Thresholds)
    models: dict[str, ModelConfig] = field(default_factory=_default_models)

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

    def model_for(self, tier: str) -> ModelConfig:
        return self.models[tier]

    def estimate_cost(self, tier: str, input_tokens: int, output_tokens: int) -> float:
        m = self.models[tier]
        return (input_tokens * m.price_in_per_1m + output_tokens * m.price_out_per_1m) / 1_000_000