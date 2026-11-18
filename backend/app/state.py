"""Everything the API needs, created once and shared by all endpoints."""

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.execution.orchestrator import Orchestrator
from app.providers.base import ModelProvider
from app.providers.factory import get_provider
from app.providers.ollama_provider import OllamaProvider
from app.routing.expert_gate import ExpertGate, MockEmbedder, OllamaEmbedder
from app.settings_store import SettingsStore
from app.storage.repository import HistoryRepository

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class AppState:
    settings: Settings
    store: SettingsStore
    provider: ModelProvider
    repository: HistoryRepository
    orchestrator: Orchestrator          # saves every run to history
    compare_orchestrator: Orchestrator  # same pipeline, but does NOT save (keeps metrics clean)
    expert_gate: ExpertGate


def build_state(
    settings: Settings,
    provider: ModelProvider,
    history_path: str | Path = "data/history.jsonl",
    settings_path: str | Path | None = "data/settings.json",
) -> AppState:
    store = SettingsStore(settings, settings_path)
    repository = HistoryRepository(history_path)
    raw_provider = provider
    while hasattr(raw_provider, "inner"):
        raw_provider = raw_provider.inner
    if isinstance(raw_provider, OllamaProvider):
        embedder = OllamaEmbedder(base_url=raw_provider.base_url)
        embedding_cache_path = _PROJECT_ROOT / "data" / "expert_embeddings.json"
    else:
        embedder = MockEmbedder()
        embedding_cache_path = _PROJECT_ROOT / "data" / "expert_embeddings.mock.json"
    expert_gate = ExpertGate(settings, embedder, cache_path=embedding_cache_path)
    if settings.use_experts:
        expert_gate.prepare()
    return AppState(
        settings=settings,
        store=store,
        provider=provider,
        repository=repository,
        orchestrator=Orchestrator(provider, settings, repository, expert_gate=expert_gate),
        compare_orchestrator=Orchestrator(provider, settings, None, expert_gate=expert_gate),
        expert_gate=expert_gate,
    )


def build_default_state() -> AppState:
    """The real app: provider from PROVIDER_MODE in .env, data saved under ./data."""
    settings = Settings()
    return build_state(settings, get_provider(settings=settings))