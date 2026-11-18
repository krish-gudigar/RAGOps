import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.errors import ProviderError
from app.providers.mock_provider import MockModelProvider
from app.settings_store import SettingsStore
from app.state import build_state

SIMPLE = "Translate 'Good morning' to French."
HARD = (
    "Debug a race condition across multiple files in our Python service. "
    "The stack trace points to the cache layer. Fix the bug, keep it "
    "compatible with Python 3.8, add unit tests, handle edge cases, and "
    "explain the root cause step by step."
)
DNS = "Explain how DNS works"   # scores 3/10 (low) with the default thresholds


class ExplodingProvider(MockModelProvider):
    def generate(self, request):
        raise AssertionError("the model must not be called")


class BrokenProvider(MockModelProvider):
    def generate(self, request):
        raise ProviderError("Could not reach Ollama. Is it running?")


def make_client(tmp_path, provider_cls=MockModelProvider):
    settings = Settings()
    state = build_state(settings, provider_cls(settings),
                        history_path=tmp_path / "history.jsonl",
                        settings_path=tmp_path / "settings.json")
    return TestClient(create_app(state)), state


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)[0]


# ---------- health and config ----------
def test_health(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "provider": "mock", "provider_mode": "mock"}


def test_config_describes_the_setup(client):
    body = client.get("/api/config").json()
    assert body["provider_mode"] == "mock"
    assert body["strategies"] == ["dynamic", "always_small", "always_strong", "expert_pool"]
    assert body["tiers"] == ["small", "medium", "strong"]
    assert set(body["models"]) == {"small", "medium", "strong"}
    assert body["settings"]["thresholds"] == {
        "low_max": 3, "medium_max": 7, "medium_context_tokens": 200, "long_context_tokens": 1000}
    assert "prototype" in body["note"]


def test_expert_gate_settings_are_exposed_and_persisted(client, tmp_path):
    settings = client.get("/api/config").json()["settings"]
    assert settings["use_experts"] is False
    assert settings["embedding_model"] == "all-minilm"
    assert settings["embedding_top_k"] == 3
    assert settings["embedding_min_score"] == 0.45
    assert settings["embedding_min_margin"] == 0.05
    assert settings["embedding_timeout_s"] == 15.0

    updated = client.post("/api/settings", json={
        "use_experts": True,
        "embedding_model": "custom-embedder",
        "embedding_top_k": 5,
        "embedding_min_score": 0.6,
        "embedding_min_margin": 0.1,
        "embedding_timeout_s": 2.5,
        "expert_models": {"coding": {"medium": "custom-coder:1.5b"}},
    })
    assert updated.status_code == 200
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["use_experts"] is True
    assert saved["embedding_model"] == "custom-embedder"
    assert saved["expert_models"]["coding"]["medium"] == "custom-coder:1.5b"

    fresh_settings = Settings()
    SettingsStore(fresh_settings, tmp_path / "settings.json")
    assert fresh_settings.expert_models[next(
        expert for expert in fresh_settings.expert_models if expert.value == "coding"
    )]["medium"] == "custom-coder:1.5b"


def test_execute_accepts_per_request_expert_override(client):
    response = client.post("/api/execute", json={
        "task": "Write a Python function to sort a list.",
        "use_experts": True,
    })
    body = response.json()
    assert response.status_code == 200
    assert body["result"]["decision"]["expert"] == "coding"
    assert body["result"]["gate_stage"] == "regex"


def test_execute_can_disable_globally_enabled_experts_per_request(tmp_path):
    client, state = make_client(tmp_path)
    state.settings.use_experts = True
    body = client.post("/api/execute", json={
        "task": "Write a Python function to sort a list.",
        "use_experts": False,
    }).json()
    assert body["result"]["decision"]["gate_stage"] is None
    assert body["result"]["decision"]["expert"] == "general"


def test_docs_page_is_available(client):
    assert client.get("/docs").status_code == 200


# ---------- analyze ----------
def test_analyze_returns_scores_and_decision_without_calling_a_model(tmp_path):
    client, _ = make_client(tmp_path, ExplodingProvider)
    body = client.post("/api/analyze", json={"task": SIMPLE}).json()
    assert body["analysis"]["difficulty"] == "low"
    assert body["analysis"]["task_type"] == "transformation"
    assert body["decision"]["selected_tier"] == "small"
    assert body["decision"]["reason"]


def test_analyze_with_baseline_strategy(client):
    body = client.post("/api/analyze", json={"task": SIMPLE, "strategy": "always_strong"}).json()
    assert body["decision"]["selected_tier"] == "strong"


def test_analyze_can_override_expert_setting(client):
    body = client.post("/api/analyze", json={
        "task": "Write a Python function to sort a list.",
        "use_experts": True,
    }).json()
    assert body["decision"]["expert"] == "coding"
    assert body["decision"]["gate_stage"] == "regex"
    assert body["decision"]["model_name"].startswith("qwen2.5-coder:")


@pytest.mark.parametrize("payload", [
    {"task": ""},
    {},
    {"task": "x", "strategy": "magic"},
])
def test_analyze_rejects_bad_input(client, payload):
    assert client.post("/api/analyze", json=payload).status_code == 422


# ---------- execute ----------
def test_execute_simple_task(client):
    body = client.post("/api/execute", json={"task": SIMPLE}).json()
    result = body["result"]
    assert result["success"] is True and result["final_tier"] == "small"
    assert result["decision"]["selected_tier"] == "small"
    assert body["timeline"][0] == "Task received"
    assert body["timeline"][-1] == "Final response returned"
    assert body["escalation_reasons"] == []


def test_execute_escalates_and_explains_why(client):
    body = client.post("/api/execute", json={"task": HARD, "strategy": "always_small"}).json()
    result = body["result"]
    assert [a["tier"] for a in result["attempts"]] == ["small", "medium", "strong"]
    assert result["was_escalated"] is True and result["success"] is True
    assert len(body["escalation_reasons"]) == 2
    assert "Escalated to the strong model" in body["timeline"]


def test_execute_respects_toggles(client):
    body = client.post("/api/execute", json={
        "task": HARD, "strategy": "always_small", "enable_escalation": False}).json()
    assert len(body["result"]["attempts"]) == 1 and body["result"]["success"] is False

    body = client.post("/api/execute", json={
        "task": HARD, "strategy": "always_small", "enable_validation": False}).json()
    assert body["result"]["attempts"][0]["validation"] is None
    assert "Validation skipped (turned off)" in body["timeline"]


def test_execute_rejects_bad_input(client):
    assert client.post("/api/execute", json={"task": ""}).status_code == 422
    assert client.post("/api/execute", json={"task": "x", "max_escalations": 5}).status_code == 422


def test_provider_failure_gives_a_clear_502(tmp_path):
    client, _ = make_client(tmp_path, BrokenProvider)
    response = client.post("/api/execute", json={"task": SIMPLE})
    assert response.status_code == 502
    assert "Is it running" in response.json()["detail"]


# ---------- compare ----------
def test_compare_runs_all_three_strategies(client):
    body = client.post("/api/compare", json={"task": HARD}).json()
    assert list(body["results"]) == ["always_small", "always_strong", "dynamic", "expert_pool"]
    rows = {row["strategy"]: row for row in body["summary"]}

    assert rows["always_small"]["final_tier"] == "small"
    assert rows["always_small"]["success"] is False      # baselines never escalate
    assert rows["always_small"]["escalations"] == 0
    assert rows["always_strong"]["final_tier"] == "strong" and rows["always_strong"]["success"]
    assert rows["dynamic"]["final_tier"] == "strong" and rows["dynamic"]["success"]
    assert rows["expert_pool"]["final_tier"] == "strong"
    assert rows["always_strong"]["estimated_cost"] > rows["always_small"]["estimated_cost"]
    assert all(row["validated"] for row in rows.values())
    assert any("ONE task" in note for note in body["notes"])


def test_compare_dynamic_can_escalate_but_baselines_cannot(client):
    task = "Explain how DNS works [mock:needs=strong]"
    rows = {r["strategy"]: r for r in client.post("/api/compare", json={"task": task}).json()["summary"]}
    assert rows["dynamic"]["escalations"] >= 1 and rows["dynamic"]["success"]
    assert rows["always_small"]["escalations"] == 0 and not rows["always_small"]["success"]


def test_compare_with_validation_off_says_so(client):
    body = client.post("/api/compare", json={"task": SIMPLE, "enable_validation": False}).json()
    assert all(row["validated"] is False for row in body["summary"])
    assert any("Validation was off" in note for note in body["notes"])


def test_compare_does_not_write_history(client):
    client.post("/api/compare", json={"task": SIMPLE})
    assert client.get("/api/history").json() == []


# ---------- history and metrics ----------
def test_history_is_newest_first_and_limited(client):
    client.post("/api/execute", json={"task": "Translate one to French."})
    client.post("/api/execute", json={"task": "Translate two to French."})
    client.post("/api/execute", json={"task": "Translate three to French."})
    history = client.get("/api/history").json()
    assert [h["result"]["task"] for h in history][0] == "Translate three to French."
    assert len(history) == 3 and history[0]["timestamp"]
    assert len(client.get("/api/history", params={"limit": 2}).json()) == 2
    assert client.get("/api/history", params={"limit": 0}).status_code == 422


def test_metrics_when_empty(client):
    body = client.get("/api/metrics").json()
    assert body["overall"]["total_tasks"] == 0 and body["overall"]["success_rate"] is None
    assert body["by_strategy"] == {}


def test_metrics_after_runs(client):
    client.post("/api/execute", json={"task": SIMPLE})
    client.post("/api/execute", json={"task": HARD, "strategy": "always_small"})
    body = client.get("/api/metrics").json()
    overall = body["overall"]
    assert overall["total_tasks"] == 2 and overall["validated_tasks"] == 2
    assert overall["escalation_rate"] == pytest.approx(0.5)
    assert overall["failed_validations"] == 2
    assert set(body["by_strategy"]) == {"dynamic", "always_small"}
    assert body["by_strategy"]["dynamic"]["total_tasks"] == 1
    assert "not general claims" in body["note"]


# ---------- settings ----------
def difficulty_of(client, task):
    return client.post("/api/analyze", json={"task": task}).json()["analysis"]["difficulty"]


def test_changing_thresholds_changes_the_analysis_immediately(client):
    assert difficulty_of(client, DNS) == "low"
    response = client.post("/api/settings", json={"thresholds": {"low_max": 2}})
    assert response.status_code == 200 and response.json()["thresholds"]["low_max"] == 2
    assert difficulty_of(client, DNS) == "medium"


def test_partial_update_leaves_other_values_alone(client):
    client.post("/api/settings", json={"assumed_output_tokens": 300})
    snap = client.get("/api/config").json()["settings"]
    assert snap["assumed_output_tokens"] == 300 and snap["thresholds"]["medium_max"] == 7


@pytest.mark.parametrize("payload", [
    {"thresholds": {"low_max": 7}},                                            # not below medium_max
    {"thresholds": {"medium_context_tokens": 2000}},                           # not below long_context
    {"thresholds": {"low_max": 99}},                                           # out of range
    {"models": {"small": {"price_in_per_1m": -1}}},
    {"models": {"huge": {"price_in_per_1m": 1}}},
    {"expert_models": {"coding": {"huge": "not-a-tier-model"}}},
    {"expert_model_prices": {"unconfigured-model": {"price_in_per_1m": 1}}},
])
def test_invalid_settings_are_rejected_and_change_nothing(client, payload):
    before = client.get("/api/config").json()["settings"]
    assert client.post("/api/settings", json=payload).status_code == 422
    assert client.get("/api/config").json()["settings"] == before


def test_price_change_changes_estimated_cost(client):
    before = client.post("/api/analyze", json={"task": SIMPLE}).json()["decision"]["estimated_cost"]
    client.post("/api/settings", json={"models": {"small": {"price_in_per_1m": 100.0}}})
    after = client.post("/api/analyze", json={"task": SIMPLE}).json()["decision"]["estimated_cost"]
    assert after > before


def test_model_names_cannot_be_changed_through_the_api(client):
    names = client.get("/api/config").json()["models"]
    client.post("/api/settings", json={"models": {"small": {"name": "evil-model"}}})
    assert client.get("/api/config").json()["models"] == names


def test_reset_restores_defaults(client):
    client.post("/api/settings", json={"thresholds": {"low_max": 2}, "assumed_output_tokens": 50})
    snap = client.post("/api/settings/reset").json()
    assert snap["thresholds"]["low_max"] == 3 and snap["assumed_output_tokens"] == 200
    assert difficulty_of(client, DNS) == "low"


def test_settings_survive_a_restart(tmp_path):
    client, _ = make_client(tmp_path)
    client.post("/api/settings", json={"thresholds": {"low_max": 2}})
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["thresholds"]["low_max"] == 2
    assert "name" not in saved["models"]["small"]

    fresh = Settings()
    SettingsStore(fresh, tmp_path / "settings.json")
    assert fresh.thresholds.low_max == 2


def test_reset_deletes_the_saved_file(tmp_path):
    client, _ = make_client(tmp_path)
    client.post("/api/settings", json={"thresholds": {"low_max": 2}})
    client.post("/api/settings/reset")
    assert not (tmp_path / "settings.json").exists()


def test_corrupt_settings_file_is_ignored(tmp_path):
    (tmp_path / "settings.json").write_text("{ not json", encoding="utf-8")
    settings = Settings()
    SettingsStore(settings, tmp_path / "settings.json")
    assert settings.thresholds.low_max == 3