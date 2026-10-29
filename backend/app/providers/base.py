"""Provider interface: the shape every model provider must follow.

The rest of the app only talks to this interface, so a mock model and a
real model can be swapped without changing any other code.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from app.models.domain import Tier


class ModelRequest(BaseModel):
    task: str
    tier: Tier
    # Hints from the analyzer. Real providers can ignore them;
    # the mock provider uses them to decide how well it "answers".
    task_type: str = "unknown"
    difficulty: Literal["low", "medium", "high"] = "medium"
    max_output_tokens: int = Field(default=512, ge=1)


class ModelResponse(BaseModel):
    text: str
    model: str
    tier: Tier
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)


class ModelInfo(BaseModel):
    provider: str
    mode: Literal["mock", "real"]
    models: dict[str, str]          # tier -> model name
    description: str = ""


class ModelProvider(Protocol):
    name: str

    def generate(self, request: ModelRequest) -> ModelResponse: ...

    def estimate_cost(self, request: ModelRequest, response: ModelResponse) -> float: ...

    def get_model_info(self) -> ModelInfo: ...