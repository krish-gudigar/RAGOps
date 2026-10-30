"""GeneralValidator: cheap sanity checks that apply to any answer.

This is a HEURISTIC check. It catches empty answers, absurdly long answers
and obvious refusal text. It cannot tell whether an answer is correct.
"""

import re

from app.models.domain import TaskAnalysis, ValidationResult
from app.validation.base import make_result

MAX_CHARS = 20_000
SHORT_CHARS = 10
REFUSAL_WINDOW = 200  # refusals appear at the START of an answer

FAILURE_PATTERNS = [
    r"\bi'?m sorry,? (but )?i (cannot|can't|can not)\b",
    r"\bi (cannot|can't|can not|am unable to|am not able to) (help|assist|answer|comply|fulfill)",
    r"\bi'm (unable|not able) to (help|assist|answer|comply|fulfill)",
    r"\bas an ai language model\b",
]


class GeneralValidator:
    name = "heuristic:general"

    def __init__(self, max_chars: int = MAX_CHARS):
        self.max_chars = max_chars

    def validate(self, task: str, response: str, analysis: TaskAnalysis) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        text = response.strip()

        if not text:
            errors.append("Response is empty.")
        else:
            if len(text) > self.max_chars:
                errors.append(f"Response is too long ({len(text)} characters, limit {self.max_chars}).")
            opening = text[:REFUSAL_WINDOW].lower().replace("\u2019", "'")
            if any(re.search(p, opening) for p in FAILURE_PATTERNS):
                errors.append("Response looks like a refusal or failure message.")
            if len(text) < SHORT_CHARS:
                warnings.append(f"Response is very short ({len(text)} characters).")

        return make_result(
            self.name, errors, warnings,
            "Heuristic check: not empty, not too long, no refusal text at the start. "
            "Does not check correctness.",
        )