import pytest

from app.execution.orchestrator import Orchestrator
from app.execution.timeline import build_timeline
from app.models.domain import ValidationResult
from app.models.requests import TaskRequest
from app.providers.mock_provider import MockModelProvider
from app.storage.repository import HistoryRepository

SIMPLE = "Translate 'Good morning' to French."
HARD = (
    "Debug a race condition across multiple files in our Python service. "
    "The stack trace points to the cache layer. Fix the bug, keep it "
    "compatible with Python 3.8, add unit tests, handle edge cases, and "
    "explain the root cause step by step."
)
NEEDS_STRONG = "Explain how DNS works [mock:needs=strong]"


def always_fail(task, response, analysis):
    return ValidationResult(valid=False, validator_type="test:always_fail", score=0.0,
                            errors=["forced failure"])


class ExplodingProvider(MockModelProvider):
    def generate(self, request):
        raise AssertionError("the model must not be called")


@pytest.fixture
def orch():
    return Orchestrator(provider=MockModelProvider())


def run(orch, task, **kwargs):
    return orch.execute(TaskRequest(task=task, **kwargs))


# ---------- analyze only ----------
def test_analyze_and_route_does_not_call_a_model():
    orch = Orchestrator(provider=ExplodingProvider())
    analysis, decision = orch.analyze_and_route(SIMPLE)
    assert analysis.difficulty == "low"
    assert decision.selected_tier == "small"


# ---------- strategies ----------
def test_simple_task_dynamic_uses_small_and_succeeds(orch):
    r = run(orch, SIMPLE)
    assert r.final_tier == "small" and len(r.attempts) == 1
    assert r.success and not r.was_escalated
    assert r.strategy == "dynamic" and r.decision.selected_tier == "small"


def test_hard_task_dynamic_uses_strong(orch):
    r = run(orch, HARD)
    assert r.analysis.difficulty == "high"
    assert r.final_tier == "strong" and r.success


def test_always_strong_uses_strong_even_for_simple_task(orch):
    r = run(orch, SIMPLE, strategy="always_strong")
    assert r.final_tier == "strong" and len(r.attempts) == 1


def test_always_small_fails_hard_task_without_escalation(orch):
    r = run(orch, HARD, strategy="always_small", enable_escalation=False)
    assert r.final_tier == "small" and not r.success and not r.was_escalated


def test_always_small_escalates_when_allowed(orch):
    r = run(orch, HARD, strategy="always_small")
    assert [a.tier for a in r.attempts] == ["small", "medium", "strong"]
    assert r.was_escalated and r.success and r.final_tier == "strong"


# ---------- escalation controls ----------
def test_max_escalations_limits_attempts(orch):
    r = run(orch, NEEDS_STRONG, strategy="always_small", max_escalations=1)
    assert len(r.attempts) == 2 and not r.success


def test_failed_validation_everywhere_gives_success_false():
    orch = Orchestrator(provider=MockModelProvider(), validate=always_fail)
    r = run(orch, SIMPLE, strategy="always_small")
    assert [a.tier for a in r.attempts] == ["small", "medium", "strong"]
    assert not r.success


# ---------- validation off ----------
def test_validation_off_skips_checks_and_never_escalates(orch):
    r = run(orch, HARD, strategy="always_small", enable_validation=False)
    assert len(r.attempts) == 1
    assert r.attempts[0].validation is None
    assert r.success  # only means "an answer came back"


# ---------- totals ----------
def test_totals_cover_every_attempt(orch):
    r = run(orch, HARD, strategy="always_small")
    assert r.total_estimated_cost == pytest.approx(sum(a.estimated_cost for a in r.attempts))
    assert r.total_latency_ms == sum(a.latency_ms for a in r.attempts)
    assert r.final_response == r.attempts[-1].response


# ---------- history ----------
def test_result_is_saved_to_history(tmp_path):
    repo = HistoryRepository(tmp_path / "h.jsonl")
    orch = Orchestrator(provider=MockModelProvider(), repository=repo)
    run(orch, SIMPLE)
    saved = repo.recent()
    assert len(saved) == 1
    assert saved[0].result.task == SIMPLE and saved[0].timestamp


# ---------- timeline ----------
def test_timeline_for_a_clean_run(orch):
    events = build_timeline(run(orch, SIMPLE))
    assert events[0] == "Task received"
    assert events[1].startswith("Task analyzed: transformation")
    assert "Dynamic routing: small model selected" in events
    assert "Validation passed" in events
    assert events[-1] == "Final response returned"
    assert not any("Escalated" in e for e in events)


def test_timeline_for_an_escalated_run(orch):
    events = build_timeline(run(orch, HARD, strategy="always_small"))
    assert "Validation failed" in events
    assert "Escalated to the medium model" in events
    assert "Escalated to the strong model" in events
    assert events.index("Escalated to the medium model") < events.index("Escalated to the strong model")
    assert events[-2] == "Validation passed"


def test_timeline_mentions_skipped_validation(orch):
    events = build_timeline(run(orch, SIMPLE, enable_validation=False))
    assert "Validation skipped (turned off)" in events