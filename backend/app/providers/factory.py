"""Choose the provider: mock (default, offline) or ollama (real local models)."""

import os

from app.config import Settings
from app.providers.mock_provider import MockModelProvider
from app.providers.ollama_provider import OllamaProvider


def get_provider(mode: str | None = None, settings: Settings | None = None):
    mode = (mode or os.getenv("PROVIDER_MODE") or "mock").strip().lower()
    if mode == "mock":
        return MockModelProvider(settings)
    if mode == "ollama":
        return OllamaProvider(settings)
    raise ValueError(f"Unknown provider mode '{mode}'. Use 'mock' or 'ollama'.")