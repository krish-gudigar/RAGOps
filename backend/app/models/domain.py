from typing import Literal
from pydantic import BaseModel, Field

Tier = Literal["small", "medium", "strong"]
Difficulty = Literal["low", "medium", "high"]


class TaskAnalysis(BaseModel):
    task_type: str
    complexity_score: int = Field(ge=0, le=2)
    reasoning_score: int = Field(ge=0, le=2)
    context_score: int = Field(ge=0, le=2)
    constraints_score: int = Field(ge=0, le=2)
    reliability_score: int = Field(ge=0, le=2)
    estimated_input_tokens: int = Field(ge=0)
    detected_constraints: list[str] = Field(default_factory=list)
    detected_signals: list[str] = Field(default_factory=list)
    total_score: int = Field(ge=0, le=10)
    difficulty: Difficulty
    explanation: str


class RoutingDecision(BaseModel):
    selected_tier: Tier
    selected_model: str
    strategy: str
    confidence: float | None = None
    reason: str
    estimated_cost: float = 0.0
    expected_latency_ms: int | None = None


class ValidationResult(BaseModel):
    valid: bool
    validator_type: str
    score: float = Field(ge=0.0, le=1.0)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explanation: str = ""


class ExecutionAttempt(BaseModel):
    attempt_number: int
    tier: Tier
    model: str
    response: str
    latency_ms: int
    estimated_cost: float
    validation: ValidationResult | None = None  # None when validation is off
    escalated: bool = False


class TaskExecutionResult(BaseModel):
    task: str
    analysis: TaskAnalysis
    attempts: list[ExecutionAttempt]
    final_response: str
    final_tier: Tier
    total_latency_ms: int
    total_estimated_cost: float
    was_escalated: bool
    success: bool