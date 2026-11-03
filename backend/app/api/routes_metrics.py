from fastapi import APIRouter, Depends, Query

from app.api.deps import get_state
from app.execution.metrics import compute_metrics
from app.models.api_models import MetricsResponse
from app.storage.repository import HistoryRecord
from app.state import AppState

router = APIRouter(prefix="/api", tags=["history and metrics"])


@router.get("/history", response_model=list[HistoryRecord])
def history(limit: int = Query(default=50, ge=1, le=500), state: AppState = Depends(get_state)):
    """Most recent saved runs, newest first."""
    return state.repository.recent(limit)


@router.get("/metrics", response_model=MetricsResponse)
def metrics(state: AppState = Depends(get_state)):
    results = state.repository.all_results()
    by_strategy = {}
    for strategy in sorted({r.strategy for r in results}):
        by_strategy[strategy] = compute_metrics([r for r in results if r.strategy == strategy])
    return MetricsResponse(
        overall=compute_metrics(results),
        by_strategy=by_strategy,
        note="Observed on the runs saved on this computer. Costs are estimates from the "
             "configured prices. These are not general claims about routing.",
    )