"""Try RouteWise with real local models (or the mock, if PROVIDER_MODE is not 'ollama')."""

from app.config import Settings
from app.execution.orchestrator import Orchestrator
from app.models.requests import TaskRequest
from app.providers.errors import ProviderError
from app.providers.factory import get_provider
from app.providers.ollama_provider import OllamaProvider

TASKS = [
    "Translate 'Good morning, how are you?' to French.",
    "Write a Python function that checks whether a number is prime.",
    "Explain why the sky is blue in three short sentences.",
]

settings = Settings()
provider = get_provider(settings=settings)
info = provider.get_model_info()
print(f"Provider: {info.provider} ({info.mode} mode)")
print("Models:  ", info.models)

try:
    if isinstance(provider, OllamaProvider):
        missing = provider.missing_models()
        if missing:
            print("\nThese models are not downloaded yet. Run:")
            for name in missing:
                print(f"  ollama pull {name}")
            raise SystemExit(1)

    orch = Orchestrator(provider=provider, settings=settings)
    for task in TASKS:
        print("\n" + "=" * 70)
        print("TASK:", task)
        result = orch.execute(TaskRequest(task=task, strategy="dynamic"))
        print(f"Routed to: {result.decision.selected_tier} ({result.decision.selected_model})")
        for a in result.attempts:
            status = "passed" if a.validation and a.validation.valid else "FAILED"
            print(f"  attempt {a.attempt_number}: {a.tier:<7} {a.latency_ms:>6} ms  validation {status}")
        print(f"Final tier: {result.final_tier} | success: {result.success} | "
              f"total {result.total_latency_ms} ms | estimated cost ${result.total_estimated_cost:.6f}")
        print("ANSWER:\n" + result.final_response.strip()[:600])
except ProviderError as error:
    print("\nProblem:", error)
    raise SystemExit(1)