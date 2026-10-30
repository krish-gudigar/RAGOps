"""RequirementValidator and FormatValidator.

Both are simple keyword / pattern checks. They are HEURISTICS: a response can
contain every keyword and still be wrong.
"""

import json
import re

from app.models.domain import TaskAnalysis, ValidationResult
from app.validation.base import make_result


class RequirementValidator:
    name = "heuristic:requirements"

    def __init__(
        self,
        required_keywords: list[str] | None = None,
        forbidden_keywords: list[str] | None = None,
        max_words: int | None = None,
    ):
        self.required_keywords = required_keywords or []
        self.forbidden_keywords = forbidden_keywords or []
        self.max_words = max_words

    def validate(self, task: str, response: str, analysis: TaskAnalysis) -> ValidationResult:
        errors: list[str] = []
        text = response.lower()

        missing = [k for k in self.required_keywords if k.lower() not in text]
        if missing:
            errors.append(f"Missing required keywords or sections: {', '.join(missing)}")

        present = [k for k in self.forbidden_keywords if k.lower() in text]
        if present:
            errors.append(f"Contains forbidden keywords: {', '.join(present)}")

        if self.max_words is not None:
            words = len(response.split())
            if words > self.max_words:
                errors.append(f"Too long: {words} words (limit {self.max_words}).")

        return make_result(
            self.name, errors, [],
            "Heuristic check: required/forbidden keywords and word limit. Case-insensitive.",
        )


_BULLET = re.compile(r"^\s*[-*\u2022]\s+\S", re.MULTILINE)
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+\S", re.MULTILINE)
_HEADING = re.compile(r"^\s*#{1,6}\s+\S", re.MULTILINE)
SUPPORTED_FORMATS = ("bullets", "numbered", "headings", "json")


class FormatValidator:
    name = "format:output"

    def __init__(self, expected_format: str):
        if expected_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unknown format '{expected_format}'. Use one of: {', '.join(SUPPORTED_FORMATS)}")
        self.expected_format = expected_format

    def validate(self, task: str, response: str, analysis: TaskAnalysis) -> ValidationResult:
        errors: list[str] = []
        fmt = self.expected_format

        if fmt == "bullets" and len(_BULLET.findall(response)) < 2:
            errors.append("Expected a bulleted list (at least 2 bullet lines).")
        elif fmt == "numbered" and len(_NUMBERED.findall(response)) < 2:
            errors.append("Expected a numbered list (at least 2 numbered lines).")
        elif fmt == "headings" and not _HEADING.search(response):
            errors.append("Expected at least one markdown heading (a line starting with #).")
        elif fmt == "json":
            try:
                json.loads(response.strip())
            except json.JSONDecodeError as exc:
                errors.append(f"Expected JSON but it does not parse (line {exc.lineno}, column {exc.colno}).")

        return make_result(self.name, errors, [], f"Format check: response should look like '{fmt}'.")