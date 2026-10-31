"""Orchestrator: runs the whole RouteWise pipeline for one task.

    task -> analyze -> route -> execute (+ validate, escalate) -> result -> log

It contains no scoring, routing or validation logic of its own. It only
connects the pieces built in earlier phases.

`success` means:
  * validation ON : the final answer passed validation.
  * validation OFF: a non-empty answer was returned (NOT checked in any way).
Metrics therefore only count validated results when computing success rates.
"""

from app.analyzer.task_analyzer import TaskAnalyzer
from app.config import Settings
from app.execution.escalation import ValidateFn, run_with_escalation, total_cost, total_latency
from app.models.domain import RoutingDecision, TaskAnalysis, TaskExecutionResult
from app.models.requests import TaskRequest
from app.providers.base import ModelProvider
from app.routing.factory import get_router
from app.storage.repository import HistoryRepository
from app.validation.pipeline import validate_response


class Orchestrator:
    def __init__(
        self,
        provider: ModelProvider,
        settings: Settings | None = None,
        repository: HistoryRepository | None = None,
        validate: ValidateFn = validate_response,
    ):
        self.provider = provider
        self.settings = settings or Settings()
        self.repository = repository
        self.validate = validate
        self.analyzer = TaskAnalyzer(self.settings.thresholds)

    def analyze_and_route(
        self, task: str, strategy: str = "dynamic"
    ) -> tuple[TaskAnalysis, RoutingDecision]:
        """Analyze and route only. No model is called (used by /api/analyze)."""
        analysis = self.analyzer.analyze(task)
        decision = get_router(strategy).route(analysis, self.settings)
        return analysis, decision

    def execute(self, request: TaskRequest) -> TaskExecutionResult:
        analysis, decision = self.analyze_and_route(request.task, request.strategy)

        attempts = run_with_escalation(
            task=request.task,
            analysis=analysis,
            start_tier=decision.selected_tier,
            provider=self.provider,
            validate=self.validate,
            enable_validation=request.enable_validation,
            enable_escalation=request.enable_escalation,
            max_escalations=request.max_escalations,
        )

        final = attempts[-1]
        if final.validation is not None:
            success = final.validation.valid
        else:
            success = bool(final.response.strip())

        result = TaskExecutionResult(
            task=request.task,
            strategy=request.strategy,
            decision=decision,
            analysis=analysis,
            attempts=attempts,
            final_response=final.response,
            final_tier=final.tier,
            total_latency_ms=total_latency(attempts),
            total_estimated_cost=total_cost(attempts),
            was_escalated=len(attempts) > 1,
            success=success,
        )
        if self.repository is not None:
            self.repository.add(result)
        return result