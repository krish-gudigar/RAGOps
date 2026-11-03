"""Everything the API needs, created once and shared by all endpoints."""

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.execution.orchestrator import Orchestrator
from app.providers.base import ModelProvider
from app.providers.factory import get_provider
from app.settings_store import SettingsStore
from app.storage.repository import HistoryRepository


@dataclass
class AppState:
    settings: Settings
    store: SettingsStore
    provider: ModelProvider
    repository: HistoryRepository
    orchestrator: Orchestrator          # saves every run to history
    compare_orchestrator: Orchestrator  # same pipeline, but does NOT save (keeps metrics clean)


def build_state(
    settings: Settings,
    provider: ModelProvider,
    history_path: str | Path = "data/history.jsonl",
    settings_path: str | Path | None = "data/settings.json",
) -> AppState:
    store = SettingsStore(settings, settings_path)
    repository = HistoryRepository(history_path)
    return AppState(
        settings=settings,
        store=store,
        provider=provider,
        repository=repository,
        orchestrator=Orchestrator(provider, settings, repository),
        compare_orchestrator=Orchestrator(provider, settings, None),
    )


def build_default_state() -> AppState:
    """The real app: provider from PROVIDER_MODE in .env, data saved under ./data."""
    settings = Settings()
    return build_state(settings, get_provider(settings=settings))