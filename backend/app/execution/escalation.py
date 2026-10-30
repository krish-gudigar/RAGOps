"""Escalation: if an answer fails validation, try the next stronger tier.

Rules:
  * Escalate only when validation is on, escalation is on, and the attempt failed.
  * Never go past the strong tier.
  * Never make more than `max_escalations` escalations.
  * Every attempt is kept, so total cost and latency include the failed ones.

`attempt.escalated` means: THIS attempt failed and caused a move to the next tier.

Not included on purpose: retrying the SAME tier. A retry rarely helps with the
mock (it is deterministic); it can be added later for real models.
"""

from collections.abc import Callable

from app.config import TIERS
from app.models.domain import ExecutionAttempt, TaskAnalysis, ValidationResult
from app.providers.base import ModelProvider, ModelRequest
from app.validation.pipeline import validate_response

ValidateFn = Callable[[str, str, TaskAnalysis], ValidationResult]


def next_tier(tier: str) -> str | None:
    """The next stronger tier, or None if `tier` is already the strongest."""
    index = TIERS.index(tier)
    return TIERS[index + 1] if index + 1 < len(TIERS) else None


def run_with_escalation(
    *,
    task: str,
    analysis: TaskAnalysis,
    start_tier: str,
    provider: ModelProvider,
    validate: ValidateFn = validate_response,
    enable_validation: bool = True,
    enable_escalation: bool = True,
    max_escalations: int = 2,
) -> list[ExecutionAttempt]:
    attempts: list[ExecutionAttempt] = []
    tier = start_tier
    escalations = 0

    while True:
        request = ModelRequest(
            task=task, tier=tier, task_type=analysis.task_type, difficulty=analysis.difficulty
        )
        response = provider.generate(request)
        cost = provider.estimate_cost(request, response)
        validation = validate(task, response.text, analysis) if enable_validation else None

        upper = next_tier(tier)
        failed = validation is not None and not validation.valid
        should_escalate = (
            failed and enable_escalation and escalations < max_escalations and upper is not None
        )

        attempts.append(
            ExecutionAttempt(
                attempt_number=len(attempts) + 1,
                tier=tier,
                model=response.model,
                response=response.text,
                latency_ms=response.latency_ms,
                estimated_cost=cost,
                validation=validation,
                escalated=should_escalate,
            )
        )

        if not should_escalate:
            return attempts
        escalations += 1
        tier = upper


def total_cost(attempts: list[ExecutionAttempt]) -> float:
    return sum(a.estimated_cost for a in attempts)


def total_latency(attempts: list[ExecutionAttempt]) -> int:
    return sum(a.latency_ms for a in attempts)


def escalation_reasons(attempts: list[ExecutionAttempt]) -> list[str]:
    """One sentence per escalation, for the UI timeline."""
    reasons = []
    for current, following in zip(attempts, attempts[1:]):
        if current.escalated:
            errors = "; ".join(current.validation.errors) if current.validation else "no details"
            reasons.append(
                f"Validation failed on the {current.tier} tier ({errors}), "
                f"so the task was escalated to the {following.tier} tier."
            )
    return reasons