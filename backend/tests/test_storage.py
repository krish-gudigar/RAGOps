import json

import pytest

from app.config import Expert
from app.execution.orchestrator import Orchestrator
from app.models.requests import TaskRequest
from app.models.domain import RoutingDecision
from app.providers.base import ModelRequest
from app.providers.mock_provider import MockModelProvider
from app.storage.answer_cache import AnswerCache, CachingProvider
from app.storage.repository import NOT_STORED, HistoryRepository


def make_result(task="Translate hello to French."):
    return Orchestrator(provider=MockModelProvider()).execute(TaskRequest(task=task))


# ---------- history ----------
def test_empty_history_when_file_missing(tmp_path):
    assert HistoryRepository(tmp_path / "none.jsonl").recent() == []


def test_add_and_read_back(tmp_path):
    repo = HistoryRepository(tmp_path / "h.jsonl")
    repo.add(make_result())
    [record] = repo.recent()
    assert record.result.task == "Translate hello to French."
    assert record.result.analysis.task_type == "transformation"


def test_recent_is_newest_first_and_respects_limit(tmp_path):
    repo = HistoryRepository(tmp_path / "h.jsonl")
    for i in range(3):
        repo.add(make_result(f"Translate word{i} to French."))
    assert repo.recent()[0].result.task == "Translate word2 to French."
    assert len(repo.recent(limit=2)) == 2
    assert len(repo.all_results()) == 3


def test_creates_missing_folders(tmp_path):
    repo = HistoryRepository(tmp_path / "a" / "b" / "h.jsonl")
    repo.add(make_result())
    assert len(repo.all_records()) == 1


def test_corrupt_lines_are_skipped(tmp_path):
    path = tmp_path / "h.jsonl"
    repo = HistoryRepository(path)
    repo.add(make_result())
    with path.open("a", encoding="utf-8") as f:
        f.write("this is not json\n")
    repo.add(make_result())
    assert len(repo.all_records()) == 2


def test_history_loads_legacy_records_without_expert_fields(tmp_path):
    result = make_result().model_copy(update={
        "decision": RoutingDecision(
            selected_tier="small", selected_model="m", strategy="dynamic", reason="legacy",
        )
    })
    payload = result.model_dump(mode="json")
    for name in ("expert", "model_name", "gate_stage", "gate_reason", "embedding_latency_ms"):
        payload.pop(name)
    for name in ("expert", "model_name", "reason", "input_tokens", "output_tokens"):
        payload["attempts"][0].pop(name)
    for name in (
        "expert", "model_name", "gate_stage", "gate_reason",
        "fallback_reason", "embedding_latency_ms", "expert_scores",
    ):
        payload["decision"].pop(name)
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        json.dumps({"timestamp": "2026-01-01T00:00:00+00:00", "result": payload}) + "\n",
        encoding="utf-8",
    )

    [record] = HistoryRepository(path).all_records()
    assert record.result.expert == Expert.GENERAL
    assert record.result.gate_stage is None
    assert record.result.attempts[0].reason == "initial"


def test_store_task_text_false_hides_text_but_keeps_numbers(tmp_path):
    repo = HistoryRepository(tmp_path / "h.jsonl", store_task_text=False)
    repo.add(make_result("Translate secret to French."))
    saved = repo.recent()[0].result
    assert saved.task == NOT_STORED and saved.final_response == NOT_STORED
    assert all(a.response == NOT_STORED for a in saved.attempts)
    assert saved.analysis.task_type == "transformation"
    assert saved.total_estimated_cost > 0
    assert "secret" not in (tmp_path / "h.jsonl").read_text(encoding="utf-8")


def test_clear_removes_history(tmp_path):
    repo = HistoryRepository(tmp_path / "h.jsonl")
    repo.add(make_result())
    repo.clear()
    assert repo.recent() == []


# ---------- answer cache ----------
class CountingMock(MockModelProvider):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        return super().generate(request)


class NoHintsMock(CountingMock):
    uses_request_hints = False


def req(
    task="Explain rainbows.", tier="small", difficulty="low",
    expert=Expert.GENERAL, model_name=None,
):
    return ModelRequest(
        task=task, tier=tier, task_type="general_question", difficulty=difficulty,
        expert=expert, model_name=model_name,
    )


def test_second_identical_request_is_served_from_cache():
    inner = CountingMock()
    provider = CachingProvider(inner, AnswerCache())
    first = provider.generate(req())
    second = provider.generate(req())
    assert inner.calls == 1
    assert first == second
    assert (provider.cache.hits, provider.cache.misses) == (1, 1)


def test_different_tier_or_task_is_a_miss():
    inner = CountingMock()
    provider = CachingProvider(inner, AnswerCache())
    provider.generate(req(tier="small"))
    provider.generate(req(tier="medium"))
    provider.generate(req(task="Something else."))
    assert inner.calls == 3 and len(provider.cache) == 3


def test_cache_does_not_collide_across_experts_or_model_names():
    inner = CountingMock()
    provider = CachingProvider(inner, AnswerCache())
    provider.generate(req(expert=Expert.CODING, model_name="coder:1b"))
    provider.generate(req(expert=Expert.REASONING, model_name="reasoner:1b"))
    provider.generate(req(expert=Expert.CODING, model_name="coder:3b"))
    assert inner.calls == 3


def test_mock_answers_depend_on_hints_so_hints_are_part_of_the_key():
    inner = CountingMock()
    provider = CachingProvider(inner, AnswerCache())
    provider.generate(req(difficulty="low"))
    provider.generate(req(difficulty="high"))
    assert inner.calls == 2


def test_providers_that_ignore_hints_share_one_entry():
    inner = NoHintsMock()
    provider = CachingProvider(inner, AnswerCache())
    provider.generate(req(difficulty="low"))
    provider.generate(req(difficulty="high"))
    assert inner.calls == 1


def test_cache_survives_restart(tmp_path):
    path = tmp_path / "cache.jsonl"
    CachingProvider(CountingMock(), AnswerCache(path)).generate(req())

    inner = CountingMock()
    reopened = CachingProvider(inner, AnswerCache(path))
    reopened.generate(req())
    assert inner.calls == 0 and reopened.cache.hits == 1


def test_cached_provider_works_inside_the_orchestrator():
    inner = CountingMock()
    orch = Orchestrator(provider=CachingProvider(inner, AnswerCache()))
    a = orch.execute(TaskRequest(task="Translate hello to French."))
    b = orch.execute(TaskRequest(task="Translate hello to French."))
    assert inner.calls == 1
    assert a.final_response == b.final_response
    assert a.total_estimated_cost == b.total_estimated_cost


def test_caching_provider_reports_inner_info():
    provider = CachingProvider(MockModelProvider(), AnswerCache())
    assert provider.name == "mock"
    assert provider.get_model_info().mode == "mock"