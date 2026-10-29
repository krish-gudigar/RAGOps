import ast
import json
import re

import pytest

from app.config import Settings
from app.providers.base import ModelRequest
from app.providers.mock_provider import MOCK_FAILURE_TEXT, MockModelProvider

provider = MockModelProvider()


def req(task="Explain photosynthesis briefly.", tier="small",
        task_type="general_question", difficulty="low"):
    return ModelRequest(task=task, tier=tier, task_type=task_type, difficulty=difficulty)


def python_block(text):
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    assert match, "no python code block found"
    return match.group(1)


# ---------- determinism ----------
def test_same_request_gives_same_response():
    r = req(tier="medium", difficulty="medium")
    assert provider.generate(r) == provider.generate(r)


# ---------- success / failure by tier ----------
@pytest.mark.parametrize("tier, difficulty", [
    ("small", "low"), ("medium", "low"), ("medium", "medium"),
    ("strong", "low"), ("strong", "medium"), ("strong", "high"),
])
def test_capable_tier_answers_well(tier, difficulty):
    text = provider.generate(req(tier=tier, difficulty=difficulty)).text
    assert MOCK_FAILURE_TEXT not in text
    assert tier in text


@pytest.mark.parametrize("tier, difficulty", [
    ("small", "medium"), ("small", "high"), ("medium", "high"),
])
def test_weak_tier_fails_on_hard_task(tier, difficulty):
    text = provider.generate(req(tier=tier, difficulty=difficulty)).text
    assert text == MOCK_FAILURE_TEXT


# ---------- the [mock:needs=...] tag ----------
def test_tag_forces_a_stricter_requirement():
    task = "Explain DNS [mock:needs=strong]"
    assert provider.generate(req(task, tier="medium", difficulty="low")).text == MOCK_FAILURE_TEXT
    assert provider.generate(req(task, tier="strong", difficulty="low")).text != MOCK_FAILURE_TEXT


def test_tag_is_not_echoed_in_the_answer():
    text = provider.generate(req("Explain DNS [mock:needs=small]", tier="small")).text
    assert "mock:needs" not in text


# ---------- answer shapes by task type ----------
def test_structured_output_success_is_valid_json():
    r = req("Return a summary as JSON.", tier="strong", task_type="structured_output", difficulty="high")
    assert json.loads(provider.generate(r).text)["status"] == "complete"


def test_structured_output_failure_is_broken_json():
    r = req("Return a summary as JSON.", tier="small", task_type="structured_output", difficulty="high")
    with pytest.raises(json.JSONDecodeError):
        json.loads(provider.generate(r).text)


def test_code_success_has_valid_python():
    r = req("Write a function.", tier="strong", task_type="coding", difficulty="high")
    ast.parse(python_block(provider.generate(r).text))   # raises if invalid


def test_code_failure_has_a_syntax_error():
    r = req("Write a function.", tier="small", task_type="coding", difficulty="high")
    with pytest.raises(SyntaxError):
        ast.parse(python_block(provider.generate(r).text))


# ---------- latency and cost ----------
def test_strong_is_slower_and_costlier_than_small():
    small = provider.generate(req(tier="small", difficulty="low"))
    strong = provider.generate(req(tier="strong", difficulty="low"))
    assert strong.latency_ms > small.latency_ms
    cost_small = provider.estimate_cost(req(tier="small"), small)
    cost_strong = provider.estimate_cost(req(tier="strong"), strong)
    assert cost_strong > cost_small


def test_cost_matches_configured_prices():
    r = req(tier="medium", difficulty="low")
    resp = provider.generate(r)
    expected = Settings().estimate_cost("medium", resp.input_tokens, resp.output_tokens)
    assert provider.estimate_cost(r, resp) == pytest.approx(expected)


def test_response_reports_model_name_and_tokens():
    resp = provider.generate(req(tier="medium", difficulty="low"))
    assert resp.model == Settings().model_for("medium").name
    assert resp.input_tokens > 0
    assert resp.output_tokens > 0


# ---------- delay ----------
def test_no_real_sleep_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr("app.providers.mock_provider.time.sleep", calls.append)
    provider.generate(req())
    assert calls == []


def test_delay_scale_sleeps_a_fraction_of_latency(monkeypatch):
    calls = []
    monkeypatch.setattr("app.providers.mock_provider.time.sleep", calls.append)
    slow = MockModelProvider(delay_scale=0.5)
    resp = slow.generate(req())
    assert calls == [pytest.approx(resp.latency_ms / 1000 * 0.5)]


# ---------- info ----------
def test_model_info_says_mock():
    info = provider.get_model_info()
    assert info.mode == "mock"
    assert set(info.models) == {"small", "medium", "strong"}