"""MockModelProvider: a fake model for offline development and tests.

HOW IT DECIDES WHETHER TO "SUCCEED":
Each tier has a capability level (small=0, medium=1, strong=2) and each task
needs a level (low=0, medium=1, high=2). If the tier is strong enough, the
mock returns a good answer; otherwise it returns a bad one.

You can force what a task needs by adding a tag to the task text:
    "Explain DNS [mock:needs=strong]"
Tiers below 'strong' will then fail on purpose. This is how we test
validation and escalation.

IMPORTANT: mock answers are fake. Results from this provider show that the
CODE works. They say nothing about how well real routing works.
"""

import json
import re
import time

from app.analyzer.token_estimator import estimate_tokens
from app.config import Settings
from app.providers.base import ModelInfo, ModelRequest, ModelResponse

TIER_LEVEL = {"small": 0, "medium": 1, "strong": 2}
DIFFICULTY_LEVEL = {"low": 0, "medium": 1, "high": 2}
NEEDS_TAG = re.compile(r"\[mock:needs=(small|medium|strong)\]", re.IGNORECASE)

# What a "failed" general answer looks like. The validators in Phase 4
# must recognise this kind of text as a failure.
MOCK_FAILURE_TEXT = "I'm sorry, I cannot help with that request."

CODE_TASK_TYPES = {"coding", "debugging"}
DETAIL_POINTS_BY_TIER = {"small": 2, "medium": 3, "strong": 4}
LATENCY_PER_OUTPUT_TOKEN_MS = 2


class MockModelProvider:
    name = "mock"

    def __init__(self, settings: Settings | None = None, delay_scale: float = 0.0):
        """delay_scale: fraction of the simulated latency to really sleep.
        0.0 (default) = no waiting, which keeps tests fast.
        Use e.g. 0.2 in the demo UI so loading spinners are visible."""
        self.settings = settings or Settings()
        self.delay_scale = delay_scale

    # ---------- public interface ----------
    def generate(self, request: ModelRequest) -> ModelResponse:
        succeeds = TIER_LEVEL[request.tier] >= self._required_level(request)
        clean_task = NEEDS_TAG.sub("", request.task).strip()
        text = self._write_answer(clean_task, request.task_type, succeeds, request.tier)

        output_tokens = estimate_tokens(text)
        latency_ms = (
            self.settings.model_for(request.tier).expected_latency_ms
            + output_tokens * LATENCY_PER_OUTPUT_TOKEN_MS
        )
        if self.delay_scale > 0:
            time.sleep(latency_ms / 1000 * self.delay_scale)

        return ModelResponse(
            text=text,
            model=self.settings.model_for(request.tier).name,
            tier=request.tier,
            input_tokens=estimate_tokens(request.task),
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

    def estimate_cost(self, request: ModelRequest, response: ModelResponse) -> float:
        return self.settings.estimate_cost(
            request.tier, response.input_tokens, response.output_tokens
        )

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider=self.name,
            mode="mock",
            models={t: self.settings.model_for(t).name for t in TIER_LEVEL},
            description="Simulated models for offline demos. Answers are fake.",
        )

    # ---------- internals ----------
    @staticmethod
    def _required_level(request: ModelRequest) -> int:
        tag = NEEDS_TAG.search(request.task)
        if tag:
            return TIER_LEVEL[tag.group(1).lower()]
        return DIFFICULTY_LEVEL[request.difficulty]

    @staticmethod
    def _topic(task: str) -> str:
        one_line = " ".join(task.split())
        return one_line[:60]

    def _write_answer(self, task: str, task_type: str, succeeds: bool, tier: str) -> str:
        topic = self._topic(task)

        if task_type == "structured_output":
            good = json.dumps({"summary": topic, "answered_by": tier, "status": "complete"})
            # Failure: cut off the closing brace and leave a trailing comma
            return good if succeeds else good[:-1] + ","

        if task_type in CODE_TASK_TYPES:
            colon = ":" if succeeds else ""   # missing colon = syntax error
            return "\n".join([
                "Here is a solution:",
                "",
                "```python",
                f"def solution(data){colon}",
                '    """Mock solution (demo only)."""',
                "    return data",
                "```",
            ])

        if not succeeds:
            return MOCK_FAILURE_TEXT

        points = [
            f"- Point {i}: a simulated detail about '{topic}'."
            for i in range(1, DETAIL_POINTS_BY_TIER[tier] + 1)
        ]
        return "\n".join([f"[mock answer from the {tier} tier] Response about: {topic}", *points])