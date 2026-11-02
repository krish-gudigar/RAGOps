"""Shared test setup.

Your real .env (Ollama model names, PROVIDER_MODE) must not change test results,
so every test starts with those variables removed. Tests that need them set them
themselves with monkeypatch.
"""

import pytest

ENVIRONMENT_VARIABLES = ("PROVIDER_MODE", "SMALL_MODEL", "MEDIUM_MODEL", "STRONG_MODEL")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)