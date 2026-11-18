import json

import httpx
import pytest

from app.config import Expert, Settings
from app.routing.expert_gate import (
    EmbeddingError,
    ExpertGate,
    MockEmbedder,
    OllamaEmbedder,
)


class CountingEmbedder:
    def __init__(self, fail=False, identical=False):
        self.calls = []
        self.fail = fail
        self.identical = identical

    def embed_many(self, texts, model, timeout_s):
        self.calls.append((list(texts), model, timeout_s))
        if self.fail:
            raise EmbeddingError("test outage")
        if self.identical:
            return [[1.0, 0.0] for _ in texts]
        return MockEmbedder().embed_many(texts, model, timeout_s)


def write_examples(path, coding="my app keeps dying after login"):
    path.write_text(
        f'coding:\n  - "{coding}"\n'
        'reasoning:\n  - "why does the total look wrong"\n'
        'general:\n  - "tell me a fun fact about birds"\n',
        encoding="utf-8",
    )


def test_specific_regex_short_circuits_embedding(tmp_path):
    embedder = CountingEmbedder()
    gate = ExpertGate(
        Settings(), embedder, tmp_path / "examples.yaml", tmp_path / "cache.json"
    )

    decision = gate.decide("Write a Python function to sort these values.")

    assert decision.expert == Expert.CODING
    assert decision.stage == "regex"
    assert "coding detected" in decision.reason
    assert not embedder.calls


def test_paraphrased_coding_prompt_uses_embedding_and_caches_examples(tmp_path):
    examples = tmp_path / "examples.yaml"
    write_examples(examples)
    embedder = CountingEmbedder()
    gate = ExpertGate(Settings(), embedder, examples, tmp_path / "cache.json")

    decision = gate.decide("my app keeps dying after login")
    assert decision.expert == Expert.CODING
    assert decision.stage == "embedding"
    assert "similarity" in decision.reason and "marg" in decision.reason
    assert decision.scores["coding"] > decision.scores["reasoning"]
    assert len(embedder.calls) == 2  # one batch for examples, one prompt

    gate.decide("the app crashes when I sign in")
    assert len(embedder.calls) == 3  # examples are reused in this gate instance


def test_low_embedding_score_falls_back_to_general(tmp_path):
    examples = tmp_path / "examples.yaml"
    write_examples(examples)
    settings = Settings()
    settings.embedding_min_score = 1.0
    gate = ExpertGate(settings, CountingEmbedder(), examples, tmp_path / "cache.json")

    decision = gate.decide("a completely unrelated phrase")

    assert decision.expert == Expert.GENERAL
    assert decision.stage == "fallback"
    assert "below" in decision.reason


def test_close_embedding_scores_fall_back_to_general(tmp_path):
    examples = tmp_path / "examples.yaml"
    write_examples(examples)
    gate = ExpertGate(
        Settings(), CountingEmbedder(identical=True), examples, tmp_path / "cache.json"
    )

    decision = gate.decide("anything at all")

    assert decision.expert == Expert.GENERAL
    assert decision.stage == "fallback"
    assert "too close" in decision.reason


def test_embedding_failure_falls_back_without_raising(tmp_path):
    examples = tmp_path / "examples.yaml"
    write_examples(examples)
    gate = ExpertGate(
        Settings(), CountingEmbedder(fail=True), examples, tmp_path / "cache.json"
    )

    decision = gate.decide("my app keeps dying after login")

    assert decision.expert == Expert.GENERAL
    assert decision.stage == "fallback"
    assert decision.reason == "embedding unavailable"


def test_embeddings_are_reused_and_recomputed_for_changed_text_or_model(tmp_path):
    examples = tmp_path / "examples.yaml"
    cache = tmp_path / "cache.json"
    write_examples(examples)
    first_embedder = CountingEmbedder()
    ExpertGate(Settings(), first_embedder, examples, cache).decide("unmatched phrase")
    stored = json.loads(cache.read_text(encoding="utf-8"))["vectors"]
    assert len(stored) == 3

    second_embedder = CountingEmbedder()
    ExpertGate(Settings(), second_embedder, examples, cache).decide("another phrase")
    assert len(second_embedder.calls) == 1  # query only; examples came from disk

    write_examples(examples, coding="my website exits after authentication")
    changed_text_embedder = CountingEmbedder()
    ExpertGate(Settings(), changed_text_embedder, examples, cache).decide("new task")
    assert len(changed_text_embedder.calls[0][0]) == 1

    changed_model = Settings()
    changed_model.embedding_model = "another-embedder"
    changed_model_embedder = CountingEmbedder()
    ExpertGate(changed_model, changed_model_embedder, examples, cache).decide("new task")
    assert len(changed_model_embedder.calls[0][0]) == 3


def test_ollama_embedder_uses_embed_endpoint_and_response_dimension():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    vectors = OllamaEmbedder("http://fake:11434", client).embed_many(
        ["prompt"], "all-minilm", 2.0
    )
    assert seen["url"] == "http://fake:11434/api/embed"
    assert seen["body"] == {"model": "all-minilm", "input": ["prompt"]}
    assert len(vectors[0]) == 3


def test_ollama_embedding_http_failure_is_reported_as_embedding_error():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(503, text="offline")
    ))
    with pytest.raises(EmbeddingError, match="embedding request failed"):
        OllamaEmbedder("http://fake:11434", client).embed_many(
            ["prompt"], "all-minilm", 1.0
        )
