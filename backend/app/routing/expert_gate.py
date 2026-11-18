"""Two-stage expert selection: specific task regexes, then local embeddings."""

import hashlib
import json
import logging
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx
import numpy as np

from app.analyzer.task_types import detect_task_type_details
from app.config import Expert, Settings, TASK_TYPE_TO_EXPERT
from app.providers.errors import ProviderError

log = logging.getLogger("routewise.expert_gate")
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_WORD_RE = re.compile(r"[a-z0-9_]+")


class EmbeddingError(Exception):
    """Raised when an embedder cannot produce a usable vector."""


class Embedder(Protocol):
    def embed_many(self, texts: list[str], model: str, timeout_s: float) -> list[list[float]]: ...


class OllamaEmbedder:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client()

    def embed_many(self, texts: list[str], model: str, timeout_s: float) -> list[list[float]]:
        try:
            response = self._client.post(
                f"{self.base_url}/api/embed",
                json={"model": model, "input": texts},
                timeout=timeout_s,
            )
            response.raise_for_status()
            payload = response.json()
            embeddings = payload["embeddings"]
            if len(embeddings) != len(texts):
                raise EmbeddingError("Ollama returned a different number of embeddings than inputs.")
            vectors = [[float(value) for value in vector] for vector in embeddings]
            if not vectors or not vectors[0] or any(len(v) != len(vectors[0]) for v in vectors):
                raise EmbeddingError("Ollama returned empty or inconsistent embedding vectors.")
            return vectors
        except httpx.TimeoutException as error:
            raise EmbeddingError("Ollama embedding request timed out.") from error
        except httpx.HTTPError as error:
            raise EmbeddingError(f"Ollama embedding request failed: {error}") from error
        except (KeyError, TypeError, ValueError) as error:
            raise EmbeddingError(f"Ollama returned an invalid embedding response: {error}") from error


class MockEmbedder:
    """Deterministic signed bag-of-words vectors for offline tests and demos."""

    dimension = 256

    @classmethod
    def _vector(cls, text: str) -> list[float]:
        vector = np.zeros(cls.dimension, dtype=float)
        words = _WORD_RE.findall(text.lower())
        for word in words:
            digest = hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % cls.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        norm = np.linalg.norm(vector)
        if norm:
            vector /= norm
        return vector.tolist()

    def embed_many(self, texts: list[str], model: str, timeout_s: float) -> list[list[float]]:
        del model, timeout_s
        return [self._vector(text) for text in texts]


@dataclass(frozen=True)
class ExpertDecision:
    expert: Expert
    stage: str
    reason: str
    embedding_latency_ms: int = 0
    scores: dict[str, float] = field(default_factory=dict)
    top_matches: tuple[tuple[str, Expert, float], ...] = ()


class ExpertGate:
    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        examples_path: str | Path | None = None,
        cache_path: str | Path | None = None,
    ):
        self.settings = settings
        self.embedder = embedder
        self.examples_path = Path(examples_path or _PROJECT_ROOT / "data" / "expert_examples.yaml")
        self.cache_path = Path(cache_path or _PROJECT_ROOT / "data" / "expert_embeddings.json")
        self.stage_counts: Counter[str] = Counter()
        self._cache_lock = threading.Lock()
        self._embedded_examples: list[tuple[str, Expert, list[float]]] | None = None

    def decide(self, task: str) -> ExpertDecision:
        started = time.perf_counter()
        match = detect_task_type_details(task)
        if match.matched_specific:
            expert = TASK_TYPE_TO_EXPERT.get(match.task_type, Expert.GENERAL)
            decision = ExpertDecision(
                expert=expert,
                stage="regex",
                reason=f"{match.task_type} detected by regex -> {expert.value} expert.",
            )
            self._record(decision.stage)
            return decision

        try:
            decision = self._embedding_decision(task, started)
        except EmbeddingError as error:
            log.warning("Expert embedding unavailable: %s", error)
            decision = ExpertDecision(
                expert=Expert.GENERAL,
                stage="fallback",
                reason="embedding unavailable",
                embedding_latency_ms=round((time.perf_counter() - started) * 1000),
            )
        self._record(decision.stage)
        return decision

    def _embedding_decision(self, task: str, started: float) -> ExpertDecision:
        examples = self._load_embedded_examples()
        prompt_vector = self.embedder.embed_many(
            [task], self.settings.embedding_model, self.settings.embedding_timeout_s
        )[0]
        query = np.asarray(prompt_vector, dtype=float)
        if query.size == 0 or not np.isfinite(query).all():
            raise EmbeddingError("Embedder returned an empty or non-finite prompt vector.")

        per_expert: dict[Expert, list[tuple[str, float]]] = {
            expert: [] for expert in Expert
        }
        for text, expert, vector in examples:
            example_vector = np.asarray(vector, dtype=float)
            if example_vector.shape != query.shape or not np.isfinite(example_vector).all():
                raise EmbeddingError("Prompt and example embedding dimensions do not match.")
            denominator = np.linalg.norm(query) * np.linalg.norm(example_vector)
            similarity = float(np.dot(query, example_vector) / denominator) if denominator else 0.0
            per_expert[expert].append((text, similarity))

        scores = {
            expert: float(np.mean(sorted((score for _, score in matches), reverse=True)[
                :self.settings.embedding_top_k
            ])) if matches else 0.0
            for expert, matches in per_expert.items()
        }
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_expert, best_score = ranked[0]
        second_expert, second_score = ranked[1]
        margin = best_score - second_score
        best_example = max(per_expert[best_expert], key=lambda item: item[1])
        latency = round((time.perf_counter() - started) * 1000)
        score_text = ", ".join(f"{e.value} {s:.2f}" for e, s in ranked)
        top_matches = tuple(
            (text, expert, score)
            for expert, matches in per_expert.items()
            for text, score in sorted(matches, key=lambda item: item[1], reverse=True)[
                :self.settings.embedding_top_k
            ]
        )
        score_map = {expert.value: score for expert, score in ranked}

        if best_score < self.settings.embedding_min_score:
            reason = (
                f"best embedding score {best_expert.value} {best_score:.2f} is below "
                f"{self.settings.embedding_min_score:.2f}; using general expert"
            )
            selected, stage = Expert.GENERAL, "fallback"
        elif margin < self.settings.embedding_min_margin:
            reason = (
                f"embedding scores too close ({best_expert.value} {best_score:.2f}, "
                f"{second_expert.value} {second_score:.2f}); using general expert"
            )
            selected, stage = Expert.GENERAL, "fallback"
        else:
            reason = (
                f"regex found no specific match; closest example '{best_example[0]}' "
                f"({best_expert.value}, similarity {best_score:.2f}, margin {margin:.2f}); "
                f"scores: {score_text}"
            )
            selected, stage = best_expert, "embedding"

        return ExpertDecision(
            expert=selected,
            stage=stage,
            reason=reason,
            embedding_latency_ms=latency,
            scores=score_map,
            top_matches=top_matches,
        )

    def _load_embedded_examples(self) -> list[tuple[str, Expert, list[float]]]:
        with self._cache_lock:
            if self._embedded_examples is not None:
                return self._embedded_examples

            examples = self._load_examples()
            cache = self._read_cache()
            result: list[tuple[str, Expert, list[float]]] = []
            missing_texts: list[str] = []
            missing_keys: list[str] = []
            missing_rows: list[int] = []
            for expert, text in examples:
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                key = f"{self.settings.embedding_model}:{text_hash}"
                vector = cache.get(key)
                if vector is None:
                    missing_texts.append(text)
                    missing_keys.append(key)
                    missing_rows.append(len(result))
                    result.append((text, expert, []))
                else:
                    result.append((text, expert, vector))

            if missing_texts:
                vectors = self.embedder.embed_many(
                    missing_texts, self.settings.embedding_model, self.settings.embedding_timeout_s
                )
                if len(vectors) != len(missing_texts):
                    raise EmbeddingError("Embedder returned a different number of vectors than examples.")
                for index, vector in enumerate(vectors):
                    if not vector or not np.isfinite(np.asarray(vector, dtype=float)).all():
                        raise EmbeddingError("Embedder returned an empty or non-finite example vector.")
                    cache[missing_keys[index]] = [float(value) for value in vector]
                    row_index = missing_rows[index]
                    text, expert, _ = result[row_index]
                    result[row_index] = (text, expert, cache[missing_keys[index]])

                self._write_cache(cache)

            self._embedded_examples = result
            return result

    def _load_examples(self) -> list[tuple[Expert, str]]:
        if not self.examples_path.exists():
            raise EmbeddingError(f"Expert example bank not found: {self.examples_path}")
        examples: list[tuple[Expert, str]] = []
        current: Expert | None = None
        for line_number, raw_line in enumerate(self.examples_path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if not raw_line[:1].isspace() and line.endswith(":"):
                try:
                    current = Expert(line[:-1])
                except ValueError as error:
                    raise EmbeddingError(f"Unknown expert at {self.examples_path}:{line_number}.") from error
                continue
            if current is None or not line.startswith("- "):
                raise EmbeddingError(f"Invalid example bank syntax at {self.examples_path}:{line_number}.")
            try:
                text = json.loads(line[2:])
            except json.JSONDecodeError as error:
                raise EmbeddingError(
                    f"Examples must be double-quoted YAML strings at {self.examples_path}:{line_number}."
                ) from error
            if not isinstance(text, str) or not text.strip():
                raise EmbeddingError(f"Empty or invalid example at {self.examples_path}:{line_number}.")
            examples.append((current, text.strip()))

        if not examples or not {expert for expert, _ in examples} >= set(Expert):
            raise EmbeddingError("Expert example bank must contain examples for coding, reasoning, and general.")
        return examples

    def _read_cache(self) -> dict[str, list[float]]:
        if not self.cache_path.exists():
            return {}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            log.warning("Ignoring corrupt embedding cache %s: %s", self.cache_path, error)
            return {}
        vectors = payload.get("vectors", {})
        if not isinstance(vectors, dict):
            raise EmbeddingError(f"Invalid embedding cache at {self.cache_path}.")
        return vectors

    def _write_cache(self, vectors: dict[str, list[float]]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"vectors": vectors}, indent=2), encoding="utf-8")
        temporary.replace(self.cache_path)

    def _record(self, stage: str) -> None:
        self.stage_counts[stage] += 1
        log.info("expert gate stage=%s count=%d", stage, self.stage_counts[stage])
