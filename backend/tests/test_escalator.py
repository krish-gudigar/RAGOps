import pytest

from app.execution.escalation import (
    escalation_reasons, next_tier, run_with_escalation, total_cost, total_latency,
)
from app.models.domain import TaskAnalysis, ValidationResult
from app.providers.mock_provider import MockModelProvider

provider = MockModelProvider()


def make_analysis(difficulty="low", task_type="general_question"):
    return TaskAnalysis(
        task_type=task_type, complexity_score=0, reasoning_score=0,
        context_score=0, constraints_score=0, reliability_score=0,
        estimated_input_tokens=10, total_score=0, difficulty=difficulty,
        explanation="test",
    )


def run(difficulty, start, **kwargs):
    return run_with_escalation(
        task="Explain how a rainbow forms.", analysis=make_analysis(difficulty),
        start_tier=start, provider=provider, **kwargs,
    )


def always_fail(task, response, analysis):
    return ValidationResult(valid=False, validator_type="test:always_fail", score=0.0,
                            errors=["forced failure"])


# ---------- next_tier ----------
def test_next_tier_order():
    assert next_tier("small") == "medium"
    assert next_tier("medium") == "strong"
    assert next_tier("strong") is None


# ---------- success without escalation ----------
def test_no_escalation_when_first_answer_is_valid():
    attempts = run("low", "small")
    assert len(attempts) == 1
    assert attempts[0].validation.valid and not attempts[0].escalated


# ---------- escalation paths ----------
def test_escalates_small_to_medium():
    attempts = run("medium", "small")
    assert [a.tier for a in attempts] == ["small", "medium"]
    assert not attempts[0].validation.valid and attempts[0].escalated
    assert attempts[1].validation.valid and not attempts[1].escalated


def test_escalates_medium_to_strong():
    attempts = run("high", "medium")
    assert [a.tier for a in attempts] == ["medium", "strong"]
    assert attempts[-1].validation.valid


def test_escalates_small_to_strong_in_two_steps():
    attempts = run("high", "small")
    assert [a.tier for a in attempts] == ["small", "medium", "strong"]
    assert [a.attempt_number for a in attempts] == [1, 2, 3]


# ---------- limits ----------
def test_never_escalates_beyond_strong():
    attempts = run("low", "small", validate=always_fail, max_escalations=5)
    assert [a.tier for a in attempts] == ["small", "medium", "strong"]
    assert not attempts[-1].escalated


def test_starting_at_strong_never_escalates():
    attempts = run("low", "strong", validate=always_fail)
    assert len(attempts) == 1 and not attempts[0].escalated


@pytest.mark.parametrize("limit, expected_attempts", [(0, 1), (1, 2), (2, 3)])
def test_respects_max_escalations(limit, expected_attempts):
    attempts = run("low", "small", validate=always_fail, max_escalations=limit)
    assert len(attempts) == expected_attempts


def test_escalation_can_be_turned_off():
    attempts = run("high", "small", enable_escalation=False)
    assert len(attempts) == 1
    assert not attempts[0].validation.valid and not attempts[0].escalated


def test_validation_off_means_no_validation_and_no_escalation():
    attempts = run("high", "small", enable_validation=False)
    assert len(attempts) == 1
    assert attempts[0].validation is None and not attempts[0].escalated


# ---------- totals ----------
def test_total_cost_adds_up_every_attempt_including_failed_ones():
    attempts = run("high", "small")
    assert total_cost(attempts) == pytest.approx(sum(a.estimated_cost for a in attempts))
    assert total_cost(attempts) > attempts[-1].estimated_cost


def test_total_latency_adds_up_every_attempt():
    attempts = run("high", "small")
    assert total_latency(attempts) == sum(a.latency_ms for a in attempts)


def test_escalating_costs_more_than_starting_at_the_right_tier():
    escalated = total_cost(run("medium", "small"))
    direct = total_cost(run("medium", "medium"))
    assert escalated > direct


# ---------- explanations ----------
def test_escalation_reasons_name_both_tiers_and_the_error():
    reasons = escalation_reasons(run("medium", "small"))
    assert len(reasons) == 1
    assert "small" in reasons[0] and "medium" in reasons[0] and "refusal" in reasons[0]


def test_no_reasons_when_nothing_escalated():
    assert escalation_reasons(run("low", "small")) == []


# ---------- other task types through the real validators ----------
def test_broken_json_triggers_escalation():
    attempts = run_with_escalation(
        task="Return a summary as JSON.", analysis=make_analysis("high", "structured_output"),
        start_tier="small", provider=provider,
    )
    assert attempts[-1].validation.valid and attempts[0].escalated


def test_code_syntax_error_triggers_escalation():
    attempts = run_with_escalation(
        task="Write a function.", analysis=make_analysis("high", "coding"),
        start_tier="small", provider=provider,
    )
    assert [a.tier for a in attempts] == ["small", "medium", "strong"]
    assert "syntax" in attempts[0].validation.errors[0].lower()