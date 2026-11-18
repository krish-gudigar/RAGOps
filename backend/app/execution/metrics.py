"""Aggregate numbers over many execution results.

All values are OBSERVED on the runs given, with ESTIMATED costs (prices come
from the configuration). They are not general claims about routing.
"""

import statistics

from pydantic import BaseModel, Field

from app.models.domain import TaskExecutionResult


class Metrics(BaseModel):
    total_tasks: int = 0
    # Tasks whose final answer was actually validated. Success rate uses only these,
    # because with validation off "success" just means "an answer came back".
    validated_tasks: int = 0
    success_rate: float | None = None
    escalation_rate: float | None = None
    failed_validations: int = 0          # attempts (not tasks) that failed validation
    average_latency_ms: float | None = None
    median_latency_ms: float | None = None
    average_estimated_cost: float | None = None
    total_estimated_cost: float = 0.0
    tasks_by_final_tier: dict[str, int] = Field(default_factory=dict)
    tasks_by_expert: dict[str, int] = Field(default_factory=dict)
    gate_stage_share: dict[str, float] = Field(default_factory=lambda: {
        "regex": 0.0, "embedding": 0.0, "fallback": 0.0,
    })
    average_gate_latency_ms_by_stage: dict[str, float] = Field(default_factory=dict)


def compute_metrics(results: list[TaskExecutionResult]) -> Metrics:
    if not results:
        return Metrics()

    n = len(results)
    validated = [r for r in results if r.attempts[-1].validation is not None]
    latencies = [r.total_latency_ms for r in results]
    costs = [r.total_estimated_cost for r in results]

    by_tier: dict[str, int] = {}
    by_expert: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    latency_by_stage: dict[str, list[int]] = {}
    for r in results:
        by_tier[r.final_tier] = by_tier.get(r.final_tier, 0) + 1
        expert = r.expert.value
        by_expert[expert] = by_expert.get(expert, 0) + 1
        if r.gate_stage:
            by_stage[r.gate_stage] = by_stage.get(r.gate_stage, 0) + 1
            latency_by_stage.setdefault(r.gate_stage, []).append(r.embedding_latency_ms)

    gated_tasks = sum(by_stage.values())
    stage_shares = {
        stage: by_stage.get(stage, 0) / gated_tasks if gated_tasks else 0.0
        for stage in ("regex", "embedding", "fallback")
    }

    return Metrics(
        total_tasks=n,
        validated_tasks=len(validated),
        success_rate=(sum(r.success for r in validated) / len(validated)) if validated else None,
        escalation_rate=sum(r.was_escalated for r in results) / n,
        failed_validations=sum(
            1 for r in results for a in r.attempts
            if a.validation is not None and not a.validation.valid
        ),
        average_latency_ms=sum(latencies) / n,
        median_latency_ms=float(statistics.median(latencies)),
        average_estimated_cost=sum(costs) / n,
        total_estimated_cost=sum(costs),
        tasks_by_final_tier=by_tier,
        tasks_by_expert=by_expert,
        gate_stage_share=stage_shares,
        average_gate_latency_ms_by_stage={
            stage: sum(latencies) / len(latencies)
            for stage, latencies in latency_by_stage.items()
        },
    )