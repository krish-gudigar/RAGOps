"""Shared test setup.

Tests must give the same results whatever is in your personal .env file
(Ollama model names, PROVIDER_MODE), so .env loading is switched off while
tests run. Tests that need those variables set them with monkeypatch.
"""

import os

# Must happen BEFORE any test module imports app.config (which calls load_dotenv).
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import pytest  # noqa: E402

ENVIRONMENT_VARIABLES = ("PROVIDER_MODE", "SMALL_MODEL", "MEDIUM_MODEL", "STRONG_MODEL")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)