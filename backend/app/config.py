"""Application settings. Thresholds are configurable, not hard-coded in logic."""

from dataclasses import dataclass


@dataclass
class Thresholds:
    # total_score <= low_max          -> "low"
    # total_score <= medium_max       -> "medium"
    # anything higher                 -> "high"
    low_max: int = 3
    medium_max: int = 7

    # Estimated input tokens that raise the context score
    medium_context_tokens: int = 200   # at or above -> context score 1
    long_context_tokens: int = 1000    # at or above -> context score 2