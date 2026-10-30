"""Validator interface and a helper for building results.

Every validator has a `name` that starts with a CATEGORY, so the UI can show
what kind of check was done:

    syntax:*     does the text parse?            (JSON, Python)
    format:*     does it have the requested shape? (bullets, headings, ...)
    test:*       did real tests run and pass?
    heuristic:*  rough rule-of-thumb checks      (NOT proof of quality)

None of these prove that an answer is factually correct.
"""

from typing import Protocol

from app.models.domain import TaskAnalysis, ValidationResult


class Validator(Protocol):
    name: str

    def validate(self, task: str, response: str, analysis: TaskAnalysis) -> ValidationResult: ...


def make_result(
    validator_type: str, errors: list[str], warnings: list[str], explanation: str
) -> ValidationResult:
    """Errors make a result invalid (score 0). Each warning lowers the score a little."""
    score = 0.0 if errors else max(0.5, 1.0 - 0.1 * len(warnings))
    return ValidationResult(
        valid=not errors,
        validator_type=validator_type,
        score=score,
        errors=errors,
        warnings=warnings,
        explanation=explanation,
    )