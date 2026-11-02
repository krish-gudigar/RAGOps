"""OllamaProvider: runs the three tiers on REAL local models through Ollama.

Ollama (https://ollama.com) runs open models on your own computer, for free.
This provider follows the same interface as the mock, so nothing else in the
app changes.

Notes
  * Settings come from .env: SMALL_MODEL, MEDIUM_MODEL, STRONG_MODEL and
    OLLAMA_BASE_URL (default http://localhost:11434).
  * temperature=0 and a fixed seed make answers as repeatable as possible.
    They are NOT guaranteed identical across computers.
  * Latency is measured on the wall clock, so the FIRST call to a model also
    includes the time to load it into memory. Call warm_up() before timing.
  * Token counts come from Ollama when it reports them; otherwise they are
    estimated.
  * Local models cost no money. The "estimated cost" is what the SAME token
    counts would cost under the prices in config.py (an assumption).
"""

import os
import time

import httpx

from app.analyzer.token_estimator import estimate_tokens
from app.config import TIERS, Settings
from app.providers.base import ModelInfo, ModelRequest, ModelResponse
from app.providers.errors import ProviderError

DEFAULT_BASE_URL = "http://localhost:11434"
PLACEHOLDER_SUFFIX = "-demo"

# The same short instruction is given to EVERY tier, so tiers are compared fairly.
SYSTEM_HINTS = {
    "structured_output": "If you are asked for JSON, reply with valid JSON only and no extra explanation.",
    "coding": "Put any Python code inside a ```python code block.",
    "debugging": "Put any Python code inside a ```python code block.",
}


class OllamaProvider:
    name = "ollama"
    uses_request_hints = False   # a real model only sees the task text

    def __init__(
        self,
        settings: Settings | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 300.0,
        keep_alive: str = "2m",
        client: httpx.Client | None = None,
    ):
        self.settings = settings or Settings()
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.keep_alive = keep_alive
        self._client = client or httpx.Client(timeout=timeout_seconds)

    # ---------- public interface ----------
    def generate(self, request: ModelRequest) -> ModelResponse:
        model = self._model_name(request.tier)
        payload = {
            "model": model,
            "prompt": request.task,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": 0, "seed": 0, "num_predict": request.max_output_tokens},
        }
        hint = SYSTEM_HINTS.get(request.task_type)
        if hint:
            payload["system"] = hint

        started = time.perf_counter()
        data = self._post("/api/generate", payload, model)
        latency_ms = round((time.perf_counter() - started) * 1000)

        text = data.get("response", "")
        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
        return ModelResponse(
            text=text,
            model=model,
            tier=request.tier,
            input_tokens=input_tokens if input_tokens is not None else estimate_tokens(request.task),
            output_tokens=output_tokens if output_tokens is not None else estimate_tokens(text),
            latency_ms=latency_ms,
        )

    def estimate_cost(self, request: ModelRequest, response: ModelResponse) -> float:
        return self.settings.estimate_cost(request.tier, response.input_tokens, response.output_tokens)

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider=self.name,
            mode="real",
            models={t: self.settings.model_for(t).name for t in TIERS},
            description=f"Local models through Ollama at {self.base_url}.",
        )

    # ---------- helpers ----------
    def installed_models(self) -> list[str]:
        """Names of the models Ollama has downloaded. Raises ProviderError if it is not running."""
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
        except httpx.RequestError as exc:
            raise self._connection_error(exc) from exc
        if response.status_code != 200:
            raise ProviderError(f"Ollama returned HTTP {response.status_code} when listing models.")
        return [m.get("name", "") for m in response.json().get("models", [])]

    def missing_models(self) -> list[str]:
        """Configured models that are not downloaded yet."""
        installed = set(self.installed_models())
        missing = []
        for tier in TIERS:
            name = self.settings.model_for(tier).name
            if name not in installed and f"{name}:latest" not in installed:
                missing.append(name)
        return missing

    def warm_up(self, tier: str) -> None:
        """Load a model into memory so the first real request is not slowed by loading."""
        self._post(
            "/api/generate",
            {"model": self._model_name(tier), "prompt": "Hi", "stream": False,
             "keep_alive": self.keep_alive, "options": {"num_predict": 1}},
            self._model_name(tier),
        )

    def _model_name(self, tier: str) -> str:
        name = self.settings.model_for(tier).name
        if name.endswith(PLACEHOLDER_SUFFIX):
            raise ProviderError(
                f"The {tier} model is still the demo placeholder '{name}'. "
                "Set SMALL_MODEL, MEDIUM_MODEL and STRONG_MODEL in your .env file."
            )
        return name

    def _post(self, path: str, payload: dict, model: str) -> dict:
        try:
            response = self._client.post(f"{self.base_url}{path}", json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"Ollama took too long to answer with '{model}'. Try a smaller model or close other programs."
            ) from exc
        except httpx.RequestError as exc:
            raise self._connection_error(exc) from exc

        if response.status_code == 404:
            raise ProviderError(f"Model '{model}' is not installed. Run:  ollama pull {model}")
        if response.status_code != 200:
            raise ProviderError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
        return response.json()

    def _connection_error(self, exc: Exception) -> ProviderError:
        return ProviderError(
            f"Could not reach Ollama at {self.base_url}. Is it running? "
            "Start the Ollama app, or switch to mock mode (PROVIDER_MODE=mock)."
        )