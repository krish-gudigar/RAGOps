"""Router interface and a helper that builds RoutingDecision objects."""

from typing import Protocol

from app.config import Expert, Settings
from app.models.domain import RoutingDecision, TaskAnalysis
from app.routing.expert_gate import ExpertDecision


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
    expert_decision: ExpertDecision | None = None,
    expert: Expert | None = None,
    fallback_reason: str | None = None,
) -> RoutingDecision:
    """Fill in model name, estimated cost and latency for a chosen tier."""
    if expert_decision is None:
        selected_expert = expert or Expert.GENERAL
    else:
        selected_expert = expert or expert_decision.expert

    if selected_expert != Expert.GENERAL:
        configured_name = settings.expert_models.get(selected_expert, {}).get(tier)
        if not configured_name:
            fallback_reason = (
                fallback_reason
                or f"No {selected_expert.value} model configured for {tier}; using the general model."
            )
            selected_expert = Expert.GENERAL

    model = settings.model_for(tier, selected_expert)
    cost = settings.estimate_cost(
        tier, analysis.estimated_input_tokens, settings.assumed_output_tokens, selected_expert
    )
    if expert_decision is None:
        combined_reason = reason
        gate_stage = None
        gate_reason = None
        embedding_latency_ms = 0
        expert_scores = {}
    else:
        gate_stage = expert_decision.stage
        gate_reason = expert_decision.reason
        embedding_latency_ms = expert_decision.embedding_latency_ms
        expert_scores = expert_decision.scores
        combined_reason = (
            f"{gate_reason} -> {selected_expert.value} expert; "
            f"score {analysis.total_score}/10 ({analysis.difficulty}) -> {tier} tier."
        )
        if fallback_reason:
            combined_reason += f" {fallback_reason}"
    return RoutingDecision(
        selected_tier=tier,
        selected_model=model.name,
        model_name=model.name,
        strategy=strategy,
        expert=selected_expert,
        gate_stage=gate_stage,
        gate_reason=gate_reason,
        fallback_reason=fallback_reason,
        embedding_latency_ms=embedding_latency_ms,
        expert_scores=expert_scores,
        confidence=confidence,
        reason=combined_reason,
        estimated_cost=cost,
        expected_latency_ms=model.expected_latency_ms,
    )