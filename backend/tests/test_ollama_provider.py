"""OllamaProvider tests. They use a SIMULATED Ollama server (httpx.MockTransport),
so they run without Ollama installed. They check our code, not real model quality."""

import json

import httpx
import pytest

from app.config import ModelConfig, Settings
from app.execution.orchestrator import Orchestrator
from app.models.requests import TaskRequest
from app.providers.base import ModelRequest
from app.providers.errors import ProviderError
from app.providers.factory import get_provider
from app.providers.mock_provider import MockModelProvider
from app.providers.ollama_provider import OllamaProvider

SETTINGS = Settings(models={
    "small": ModelConfig("tiny:0.5b", 0.10, 0.40, 400),
    "medium": ModelConfig("mid:1.5b", 0.50, 1.50, 1200),
    "strong": ModelConfig("big:3b", 3.00, 15.00, 3000),
})


def make_provider(handler, settings=SETTINGS):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaProvider(settings, base_url="http://fake:11434", client=client)


def ok_handler(text="Hello from the model.", **extra):
    def handler(request):
        return httpx.Response(200, json={"response": text, "done": True, **extra})
    return handler


def req(task="Say hi.", tier="small", task_type="general_question"):
    return ModelRequest(task=task, tier=tier, task_type=task_type, difficulty="low")


# ---------- request / response ----------
def test_sends_the_expected_request():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": "ok"})

    make_provider(handler).generate(req("What is DNS?", tier="medium"))
    body = seen["body"]
    assert seen["url"] == "http://fake:11434/api/generate"
    assert body["model"] == "mid:1.5b"
    assert body["prompt"] == "What is DNS?"
    assert body["stream"] is False
    assert body["options"]["temperature"] == 0
    assert body["options"]["num_predict"] == 512
    assert "system" not in body


def test_uses_token_counts_reported_by_ollama():
    provider = make_provider(ok_handler("answer", prompt_eval_count=11, eval_count=22))
    resp = provider.generate(req())
    assert (resp.input_tokens, resp.output_tokens) == (11, 22)
    assert resp.text == "answer" and resp.model == "tiny:0.5b" and resp.tier == "small"


def test_estimates_tokens_when_ollama_does_not_report_them():
    resp = make_provider(ok_handler("a" * 400)).generate(req("b" * 80))
    assert resp.output_tokens > 0 and resp.input_tokens > 0


def test_latency_is_measured():
    resp = make_provider(ok_handler("x")).generate(req())
    assert isinstance(resp.latency_ms, int) and resp.latency_ms >= 0


def test_cost_uses_configured_prices():
    provider = make_provider(ok_handler("x", prompt_eval_count=1000, eval_count=1000))
    r = req(tier="strong")
    resp = provider.generate(r)
    assert provider.estimate_cost(r, resp) == pytest.approx(0.018)


def test_system_hint_added_for_code_and_json_tasks_only():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"response": "ok"})

    provider = make_provider(handler)
    provider.generate(req(task_type="coding"))
    provider.generate(req(task_type="structured_output"))
    provider.generate(req(task_type="summarization"))
    assert "```python" in bodies[0]["system"]
    assert "JSON" in bodies[1]["system"]
    assert "system" not in bodies[2]


# ---------- errors ----------
def test_ollama_not_running_gives_a_helpful_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderError, match="Is it running"):
        make_provider(handler).generate(req())


def test_missing_model_tells_you_the_pull_command():
    def handler(request):
        return httpx.Response(404, json={"error": "model not found"})

    with pytest.raises(ProviderError, match="ollama pull tiny:0.5b"):
        make_provider(handler).generate(req())


def test_timeout_gives_a_helpful_error():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ProviderError, match="too long"):
        make_provider(handler).generate(req())


def test_other_http_errors_are_reported():
    def handler(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(ProviderError, match="HTTP 500"):
        make_provider(handler).generate(req())


def test_placeholder_model_names_are_rejected_without_calling_ollama():
    def handler(request):
        raise AssertionError("must not be called")

    with pytest.raises(ProviderError, match=".env"):
        make_provider(handler, settings=Settings()).generate(req())


# ---------- info and helpers ----------
def test_model_info_says_real_mode():
    info = make_provider(ok_handler()).get_model_info()
    assert info.mode == "real" and info.provider == "ollama"
    assert info.models == {"small": "tiny:0.5b", "medium": "mid:1.5b", "strong": "big:3b"}


def tags_handler(names):
    def handler(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": n} for n in names]})
    return handler


def test_installed_and_missing_models():
    provider = make_provider(tags_handler(["tiny:0.5b", "mid:1.5b"]))
    assert provider.installed_models() == ["tiny:0.5b", "mid:1.5b"]
    assert provider.missing_models() == ["big:3b"]


def test_latest_tag_counts_as_installed():
    settings = Settings(models={
        "small": ModelConfig("llama3.2", 0.1, 0.4, 400),
        "medium": ModelConfig("llama3.2", 0.5, 1.5, 1200),
        "strong": ModelConfig("llama3.2", 3.0, 15.0, 3000),
    })
    assert make_provider(tags_handler(["llama3.2:latest"]), settings).missing_models() == []


def test_warm_up_loads_the_right_model():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"response": ""})

    make_provider(handler).warm_up("strong")
    assert seen[0]["model"] == "big:3b" and seen[0]["options"]["num_predict"] == 1


# ---------- plugs into the rest of the app unchanged ----------
def test_orchestrator_escalates_with_the_ollama_provider():
    """Simulated server: the small model refuses, the others answer."""

    def handler(request):
        model = json.loads(request.content)["model"]
        if model == "tiny:0.5b":
            return httpx.Response(200, json={"response": "I'm sorry, I cannot help with that request."})
        return httpx.Response(200, json={"response": f"Answer from {model}.", "prompt_eval_count": 5, "eval_count": 5})

    orch = Orchestrator(provider=make_provider(handler), settings=SETTINGS)
    result = orch.execute(TaskRequest(task="Translate hello to French.", strategy="always_small"))
    assert [a.tier for a in result.attempts] == ["small", "medium"]
    assert result.success and result.final_response == "Answer from mid:1.5b."
    assert result.total_estimated_cost > 0


# ---------- factory ----------
def test_factory_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("PROVIDER_MODE", raising=False)
    assert isinstance(get_provider(), MockModelProvider)


def test_factory_reads_environment(monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "ollama")
    assert isinstance(get_provider(), OllamaProvider)


def test_factory_argument_wins_over_environment(monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "ollama")
    assert isinstance(get_provider("mock"), MockModelProvider)


def test_factory_rejects_unknown_mode():
    with pytest.raises(ValueError):
        get_provider("magic")