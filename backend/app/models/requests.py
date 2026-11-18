from typing import Literal
from pydantic import BaseModel, Field

Strategy = Literal["dynamic", "always_small", "always_strong", "expert_pool"]


class TaskRequest(BaseModel):
    task: str = Field(min_length=1)
    strategy: Strategy = "dynamic"
    use_experts: bool | None = None
    enable_validation: bool = True
    enable_escalation: bool = True
    max_escalations: int = Field(default=2, ge=0, le=2)
    selected_provider: str | None = None