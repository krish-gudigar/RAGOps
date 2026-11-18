import pytest

from app.execution.metrics import Metrics, compute_metrics
from app.config import Expert
from app.models.domain import (
    ExecutionAttempt, TaskAnalysis, TaskExecutionResult, ValidationResult,
)


def analysis():
    return TaskAnalysis(
        task_type="general_question", complexity_score=0, reasoning_score=0,
        context_score=0, constraints_score=0, reliability_score=0,
        estimated_input_tokens=5, total_score=0, difficulty="low", explanation="t",
    )


def attempt(n, tier, valid):
    validation = None if valid is None else ValidationResult(
        valid=valid, validator_type="x", score=1.0 if valid else 0.0)
    return ExecutionAttempt(attempt_number=n, tier=tier, model="m", response="r",
                            latency_ms=0, estimated_cost=0.0, validation=validation)


def make_result(
    latency, cost, final_valid, failed_before=0, tier="small",
    expert=Expert.GENERAL, gate_stage=None, gate_latency=0,
):
    """final_valid: True / False, or None when validation was off."""
    attempts = [attempt(i + 1, "small", False) for i in range(failed_before)]
    attempts.append(attempt(failed_before + 1, tier, final_valid))
    return TaskExecutionResult(
        task="t", analysis=analysis(), attempts=attempts, final_response="r",
        final_tier=tier, total_latency_ms=latency, total_estimated_cost=cost,
        was_escalated=failed_before > 0,
        success=True if final_valid is None else final_valid,
        expert=expert,
        gate_stage=gate_stage,
        embedding_latency_ms=gate_latency,
    )


def test_empty_results_give_empty_metrics():
    m = compute_metrics([])
    assert m == Metrics()
    assert m.success_rate is None and m.total_tasks == 0


def test_metrics_values():
    results = [
        make_result(100, 0.01, True),
        make_result(300, 0.03, False, failed_before=1, tier="medium"),
        make_result(200, 0.02, True),
    ]
    m = compute_metrics(results)
    assert m.total_tasks == 3 and m.validated_tasks == 3
    assert m.success_rate == pytest.approx(2 / 3)
    assert m.escalation_rate == pytest.approx(1 / 3)
    assert m.failed_validations == 2
    assert m.average_latency_ms == pytest.approx(200)
    assert m.median_latency_ms == 200
    assert m.average_estimated_cost == pytest.approx(0.02)
    assert m.total_estimated_cost == pytest.approx(0.06)
    assert m.tasks_by_final_tier == {"small": 2, "medium": 1}


def test_success_rate_ignores_results_without_validation():
    results = [make_result(100, 0.01, None), make_result(100, 0.01, False)]
    m = compute_metrics(results)
    assert m.total_tasks == 2 and m.validated_tasks == 1
    assert m.success_rate == 0.0


def test_success_rate_is_none_when_nothing_was_validated():
    m = compute_metrics([make_result(100, 0.01, None)])
    assert m.success_rate is None
    assert m.escalation_rate == 0.0


def test_median_with_even_count():
    m = compute_metrics([make_result(100, 0, True), make_result(300, 0, True)])
    assert m.median_latency_ms == 200


def test_metrics_report_expert_breakdown_and_gate_stage_shares_and_latency():
    results = [
        make_result(100, 0, True, expert=Expert.CODING, gate_stage="regex"),
        make_result(100, 0, True, expert=Expert.REASONING, gate_stage="embedding", gate_latency=24),
        make_result(100, 0, True, expert=Expert.GENERAL, gate_stage="fallback", gate_latency=40),
        make_result(100, 0, True),
    ]
    metrics = compute_metrics(results)
    assert metrics.tasks_by_expert == {"coding": 1, "reasoning": 1, "general": 2}
    assert metrics.gate_stage_share == {
        "regex": pytest.approx(1 / 3),
        "embedding": pytest.approx(1 / 3),
        "fallback": pytest.approx(1 / 3),
    }
    assert metrics.average_gate_latency_ms_by_stage == {
        "regex": 0.0, "embedding": 24.0, "fallback": 40.0,
    }