"""Request and response shapes used only by the HTTP API.

The core shapes (TaskAnalysis, RoutingDecision, TaskExecutionResult ...) live in
domain.py. These wrap them for the endpoints.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.execution.metrics import Metrics
from app.models.domain import RoutingDecision, TaskAnalysis, TaskExecutionResult, Tier
from app.models.requests import Strategy


# ---------- analyze / execute ----------
class AnalyzeRequest(BaseModel):
    task: str = Field(min_length=1)
    strategy: Strategy = "dynamic"


class AnalyzeResponse(BaseModel):
    analysis: TaskAnalysis
    decision: RoutingDecision


class ExecuteResponse(BaseModel):
    result: TaskExecutionResult
    timeline: list[str]
    escalation_reasons: list[str]


# ---------- compare ----------
class CompareRequest(BaseModel):
    task: str = Field(min_length=1)
    enable_validation: bool = True
    enable_escalation: bool = True   # applies to dynamic routing only; baselines never escalate
    max_escalations: int = Field(default=2, ge=0, le=2)


class CompareRow(BaseModel):
    strategy: str
    final_tier: Tier
    final_model: str
    success: bool
    validated: bool                  # False when validation was off ("success" is then meaningless)
    latency_ms: int
    estimated_cost: float
    attempts: int
    escalations: int


class CompareResponse(BaseModel):
    task: str
    results: dict[str, ExecuteResponse]
    summary: list[CompareRow]
    notes: list[str]


# ---------- history / metrics ----------
class MetricsResponse(BaseModel):
    overall: Metrics
    by_strategy: dict[str, Metrics]
    note: str


# ---------- settings ----------
class ThresholdValues(BaseModel):
    low_max: int
    medium_max: int
    medium_context_tokens: int
    long_context_tokens: int


class ModelSettings(BaseModel):
    name: str                         # read-only here: change SMALL_MODEL etc. in .env
    price_in_per_1m: float
    price_out_per_1m: float
    expected_latency_ms: int


class SettingsSnapshot(BaseModel):
    thresholds: ThresholdValues
    raise_small_for_high_reliability: bool
    assumed_output_tokens: int
    models: dict[str, ModelSettings]


class ThresholdsUpdate(BaseModel):
    low_max: int | None = Field(default=None, ge=0, le=9)
    medium_max: int | None = Field(default=None, ge=1, le=10)
    medium_context_tokens: int | None = Field(default=None, ge=1)
    long_context_tokens: int | None = Field(default=None, ge=1)


class ModelSettingsUpdate(BaseModel):
    price_in_per_1m: float | None = Field(default=None, ge=0)
    price_out_per_1m: float | None = Field(default=None, ge=0)
    expected_latency_ms: int | None = Field(default=None, ge=0)


class SettingsUpdate(BaseModel):
    """Send only what you want to change."""

    thresholds: ThresholdsUpdate | None = None
    raise_small_for_high_reliability: bool | None = None
    assumed_output_tokens: int | None = Field(default=None, ge=1, le=4096)
    models: dict[Tier, ModelSettingsUpdate] | None = None


# ---------- config / health ----------
class ConfigResponse(BaseModel):
    provider: str
    provider_mode: Literal["mock", "real"]
    provider_description: str
    strategies: list[str]
    tiers: list[str]
    models: dict[str, str]
    settings: SettingsSnapshot
    note: str


class HealthResponse(BaseModel):
    status: str
    provider: str
    provider_mode: Literal["mock", "real"]