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
from app.routing.expert_gate import ExpertGate
from app.storage.repository import HistoryRepository
from app.validation.pipeline import validate_response


class Orchestrator:
    def __init__(
        self,
        provider: ModelProvider,
        settings: Settings | None = None,
        repository: HistoryRepository | None = None,
        validate: ValidateFn = validate_response,
        expert_gate: ExpertGate | None = None,
    ):
        self.provider = provider
        self.settings = settings or Settings()
        self.repository = repository
        self.validate = validate
        self.expert_gate = expert_gate
        self.analyzer = TaskAnalyzer(self.settings.thresholds)

    def analyze_and_route(
        self, task: str, strategy: str = "dynamic", use_experts: bool | None = None,
    ) -> tuple[TaskAnalysis, RoutingDecision]:
        """Analyze and route only. No model is called (used by /api/analyze)."""
        analysis = self.analyzer.analyze(task)
        expert_decision = None
        if strategy == "dynamic" and (
            self.settings.use_experts if use_experts is None else use_experts
        ):
            if self.expert_gate is None:
                raise RuntimeError("Expert routing is enabled but no expert gate is configured.")
            expert_decision = self.expert_gate.decide(task)
        router = get_router(strategy)
        if strategy == "dynamic":
            decision = router.route(analysis, self.settings, expert_decision)
        else:
            decision = router.route(analysis, self.settings)
        return analysis, decision

    def execute(self, request: TaskRequest) -> TaskExecutionResult:
        analysis, decision = self.analyze_and_route(
            request.task, request.strategy, request.use_experts
        )

        attempts = run_with_escalation(
            task=request.task,
            analysis=analysis,
            start_tier=decision.selected_tier,
            provider=self.provider,
            validate=self.validate,
            enable_validation=request.enable_validation,
            enable_escalation=request.enable_escalation,
            max_escalations=request.max_escalations,
            start_expert=decision.expert,
            model_name=decision.model_name,
            settings=self.settings,
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
            expert=decision.expert,
            model_name=decision.model_name,
            gate_stage=decision.gate_stage,
            gate_reason=decision.gate_reason,
            embedding_latency_ms=decision.embedding_latency_ms,
        )
        if self.repository is not None:
            self.repository.add(result)
        return result