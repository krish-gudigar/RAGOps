"""Run ONE task on every tier (no escalation) and compare speed, answer and validation."""

import re
import sys

from app.analyzer.task_analyzer import TaskAnalyzer
from app.config import Settings
from app.providers.base import ModelRequest
from app.providers.errors import ProviderError
from app.providers.factory import get_provider
from app.validation.pipeline import validate_response

task = " ".join(sys.argv[1:]) or "Explain why the sky is blue in three short sentences."

settings = Settings()
provider = get_provider(settings=settings)
analysis = TaskAnalyzer(settings.thresholds).analyze(task)
print(f"Provider: {provider.get_model_info().provider} | TASK: {task}")
print(f"Analyzer: {analysis.task_type}, score {analysis.total_score}/10 ({analysis.difficulty}), "
      f"constraints found: {analysis.detected_constraints or 'none'}")

try:
    for tier in ("small", "medium", "strong"):
        request = ModelRequest(task=task, tier=tier, task_type=analysis.task_type,
                               difficulty=analysis.difficulty)
        response = provider.generate(request)
        verdict = validate_response(task, response.text, analysis)
        sentences = len([s for s in re.split(r"[.!?]+(?:\s|$)", response.text.strip()) if s.strip()])
        print("\n" + "-" * 70)
        print(f"{tier.upper()} ({response.model}): {response.latency_ms} ms, "
              f"{response.output_tokens} output tokens, ~{sentences} sentences, "
              f"validation {'passed' if verdict.valid else 'FAILED'}")
        print(response.text.strip()[:500])
except ProviderError as error:
    print("\nProblem:", error)