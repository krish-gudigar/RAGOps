from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_state
from app.config import TIERS
from app.models.api_models import ConfigResponse, SettingsSnapshot, SettingsUpdate
from app.models.requests import Strategy
from app.state import AppState
from typing import get_args

router = APIRouter(prefix="/api", tags=["config and settings"])

NOTE = ("RouteWise is an experimental, local, educational prototype. The router does not "
        "guarantee correctness, and validation does not prove factual correctness. "
        "Estimated costs depend on the configured prices.")


@router.get("/config", response_model=ConfigResponse)
def config(state: AppState = Depends(get_state)):
    info = state.provider.get_model_info()
    return ConfigResponse(
        provider=info.provider,
        provider_mode=info.mode,
        provider_description=info.description,
        strategies=list(get_args(Strategy)),
        tiers=list(TIERS),
        models=info.models,
        settings=state.store.snapshot(),
        note=NOTE,
    )


@router.post("/settings", response_model=SettingsSnapshot)
def update_settings(update: SettingsUpdate, state: AppState = Depends(get_state)):
    """Change thresholds, prices and demo settings. Send only the fields to change."""
    try:
        return state.store.apply(update)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/settings/reset", response_model=SettingsSnapshot)
def reset_settings(state: AppState = Depends(get_state)):
    return state.store.reset()