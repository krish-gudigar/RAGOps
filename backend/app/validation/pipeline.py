"""Pick the right validators for a task and combine their results.

The combined result is valid only if EVERY validator passes. The explanation
always reminds the reader that validation is not proof of correctness.
"""

from dataclasses import dataclass, field

from app.models.domain import TaskAnalysis, ValidationResult
from app.validation.base import Validator
from app.validation.code import CodeValidator
from app.validation.general import GeneralValidator
from app.validation.json_schema import StructuredOutputValidator
from app.validation.requirements import FormatValidator, RequirementValidator


@dataclass
class ValidationExtras:
    """Optional, task-specific checks (the evaluation set fills these in)."""

    required_keywords: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)
    max_words: int | None = None
    required_json_fields: list[str] = field(default_factory=list)
    expected_format: str | None = None
    test_code: str | None = None
    allow_code_execution: bool = False


def build_validators(analysis: TaskAnalysis, extras: ValidationExtras | None = None) -> list[Validator]:
    extras = extras or ValidationExtras()
    validators: list[Validator] = [GeneralValidator()]

    if analysis.task_type == "structured_output":
        validators.append(StructuredOutputValidator(extras.required_json_fields))
    if analysis.task_type in ("coding", "debugging"):
        validators.append(
            CodeValidator(
                # A debugging question may be answered in prose, so only
                # "write code" tasks must contain a code block.
                require_code_block=analysis.task_type == "coding",
                test_code=extras.test_code,
                allow_execution=extras.allow_code_execution,
            )
        )
    if extras.required_keywords or extras.forbidden_keywords or extras.max_words is not None:
        validators.append(
            RequirementValidator(extras.required_keywords, extras.forbidden_keywords, extras.max_words)
        )
    if extras.expected_format:
        validators.append(FormatValidator(extras.expected_format))
    return validators


def validate_response(
    task: str, response: str, analysis: TaskAnalysis, extras: ValidationExtras | None = None
) -> ValidationResult:
    results = [v.validate(task, response, analysis) for v in build_validators(analysis, extras)]

    types = [r.validator_type for r in results]
    return ValidationResult(
        valid=all(r.valid for r in results),
        validator_type="+".join(types),
        score=sum(r.score for r in results) / len(results),
        errors=[f"[{r.validator_type}] {e}" for r in results for e in r.errors],
        warnings=[f"[{r.validator_type}] {w}" for r in results for w in r.warnings],
        explanation=(
            f"Checks run: {', '.join(types)}. These checks look at syntax, format, "
            "tests or rough heuristics. They do not prove the answer is factually correct."
        ),
    )