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


def compute_metrics(results: list[TaskExecutionResult]) -> Metrics:
    if not results:
        return Metrics()

    n = len(results)
    validated = [r for r in results if r.attempts[-1].validation is not None]
    latencies = [r.total_latency_ms for r in results]
    costs = [r.total_estimated_cost for r in results]

    by_tier: dict[str, int] = {}
    for r in results:
        by_tier[r.final_tier] = by_tier.get(r.final_tier, 0) + 1

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
    )