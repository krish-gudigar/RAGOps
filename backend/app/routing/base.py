"""Router interface and a helper that builds RoutingDecision objects."""

from typing import Protocol

from app.config import Settings
from app.models.domain import RoutingDecision, TaskAnalysis


class Router(Protocol):
    """Anything with a `name` and a `route` method is a router."""

    name: str

    def route(self, analysis: TaskAnalysis, settings: Settings) -> RoutingDecision: ...


def build_decision(
    tier: str,
    strategy: str,
    reason: str,
    analysis: TaskAnalysis,
    settings: Settings,
    confidence: float | None = None,
) -> RoutingDecision:
    """Fill in model name, estimated cost and latency for a chosen tier."""
    model = settings.model_for(tier)
    cost = settings.estimate_cost(
        tier, analysis.estimated_input_tokens, settings.assumed_output_tokens
    )
    return RoutingDecision(
        selected_tier=tier,
        selected_model=model.name,
        strategy=strategy,
        confidence=confidence,
        reason=reason,
        estimated_cost=cost,
        expected_latency_ms=model.expected_latency_ms,
    )