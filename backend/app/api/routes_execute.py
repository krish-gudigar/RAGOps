from fastapi import APIRouter, Depends

from app.api.deps import get_state
from app.execution.escalation import escalation_reasons
from app.execution.timeline import build_timeline
from app.models.api_models import CompareRequest, CompareResponse, CompareRow, ExecuteResponse
from app.models.domain import TaskExecutionResult
from app.models.requests import TaskRequest
from app.state import AppState

router = APIRouter(prefix="/api", tags=["execute"])

COMPARE_STRATEGIES = ("always_small", "always_strong", "dynamic", "expert_pool")


def _wrap(result: TaskExecutionResult) -> ExecuteResponse:
    return ExecuteResponse(
        result=result,
        timeline=build_timeline(result),
        escalation_reasons=escalation_reasons(result.attempts),
    )


@router.post("/execute", response_model=ExecuteResponse)
def execute(request: TaskRequest, state: AppState = Depends(get_state)):
    """Analyze, route, run, validate and (optionally) escalate. The run is saved to history."""
    return _wrap(state.orchestrator.execute(request))


@router.post("/compare", response_model=CompareResponse)
def compare(request: CompareRequest, state: AppState = Depends(get_state)):
    """Compare baseline, dynamic, and expert-pool routing. Not saved to history."""
    results: dict[str, ExecuteResponse] = {}
    for strategy in COMPARE_STRATEGIES:
        is_baseline = strategy in {"always_small", "always_strong"}
        task_request = TaskRequest(
            task=request.task,
            strategy=strategy,
            use_experts=True if strategy == "expert_pool" else None,
            enable_validation=request.enable_validation,
            enable_escalation=False if is_baseline else request.enable_escalation,
            max_escalations=request.max_escalations,
        )
        results[strategy] = _wrap(state.compare_orchestrator.execute(task_request))

    summary = []
    for strategy, response in results.items():
        r = response.result
        final = r.attempts[-1]
        summary.append(CompareRow(
            strategy=strategy,
            final_tier=r.final_tier,
            final_model=final.model,
            success=r.success,
            validated=final.validation is not None,
            latency_ms=r.total_latency_ms,
            estimated_cost=r.total_estimated_cost,
            attempts=len(r.attempts),
            escalations=len(r.attempts) - 1,
        ))

    notes = [
        "Always-small and always-strong are baselines: they never escalate.",
        "This is ONE task on ONE run. It does not show that routing saves money or "
        "improves quality in general.",
        "Costs are estimates based on the configured prices.",
        "Success means the final answer passed the validators. Validation is not proof "
        "of factual correctness.",
    ]
    if not request.enable_validation:
        notes.append("Validation was off, so 'success' only means an answer came back.")
    return CompareResponse(task=request.task, results=results, summary=summary, notes=notes)