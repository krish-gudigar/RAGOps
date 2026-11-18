"""Answer cache: remember what each model tier answered for each task.

Why: for the evaluation we want to run every task on every tier ONCE, save the
answers, and then compare routers by REPLAYING them. No model is called again.

`CachingProvider` wraps any provider. A repeated request is answered from the
cache (with the originally recorded latency), so replayed results keep the
latency that was really measured.
"""

import hashlib
import json
from pathlib import Path

from app.providers.base import ModelInfo, ModelProvider, ModelRequest, ModelResponse


def make_key(provider: ModelProvider, request: ModelRequest) -> str:
    parts = {
        "provider": provider.name,
        "model": provider.get_model_info().models.get(request.tier),
        "tier": request.tier,
        "expert": request.expert.value,
        "model_name": request.model_name or provider.get_model_info().models.get(request.tier),
        "task": request.task,
        "max_output_tokens": request.max_output_tokens,
    }
    # Real models only see the task text. The mock also reads the analyzer's hints.
    if getattr(provider, "uses_request_hints", False):
        parts["task_type"] = request.task_type
        parts["difficulty"] = request.difficulty
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()


class AnswerCache:
    def __init__(self, path: str | Path | None = None):
        """path=None keeps the cache in memory only."""
        self.path = Path(path) if path else None
        self.hits = 0
        self.misses = 0
        self._entries: dict[str, ModelResponse] = {}
        if self.path and self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                        self._entries[row["key"]] = ModelResponse.model_validate(row["response"])
                    except (ValueError, KeyError):
                        continue

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: str) -> ModelResponse | None:
        return self._entries.get(key)

    def put(self, key: str, response: ModelResponse) -> None:
        self._entries[key] = response
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "response": response.model_dump()}) + "\n")


class CachingProvider:
    """Looks like any other provider, so nothing else needs to change."""

    def __init__(self, inner: ModelProvider, cache: AnswerCache):
        self.inner = inner
        self.cache = cache
        self.name = inner.name
        self.uses_request_hints = getattr(inner, "uses_request_hints", False)

    def generate(self, request: ModelRequest) -> ModelResponse:
        key = make_key(self.inner, request)
        cached = self.cache.get(key)
        if cached is not None:
            self.cache.hits += 1
            return cached
        self.cache.misses += 1
        response = self.inner.generate(request)
        self.cache.put(key, response)
        return response

    def estimate_cost(self, request: ModelRequest, response: ModelResponse) -> float:
        return self.inner.estimate_cost(request, response)

    def get_model_info(self) -> ModelInfo:
        return self.inner.get_model_info()