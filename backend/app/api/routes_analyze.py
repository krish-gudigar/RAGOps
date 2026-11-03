from fastapi import APIRouter, Depends

from app.api.deps import get_state
from app.models.api_models import AnalyzeRequest, AnalyzeResponse
from app.state import AppState

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, state: AppState = Depends(get_state)):
    """Score the task and show which tier would be chosen. No model is called."""
    analysis, decision = state.orchestrator.analyze_and_route(request.task, request.strategy)
    return AnalyzeResponse(analysis=analysis, decision=decision)