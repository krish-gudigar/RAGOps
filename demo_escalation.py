from app.execution.escalation import escalation_reasons, run_with_escalation, total_cost, total_latency
from app.models.domain import TaskAnalysis
from app.providers.mock_provider import MockModelProvider

analysis = TaskAnalysis(
    task_type="general_question", complexity_score=0, reasoning_score=0,
    context_score=0, constraints_score=0, reliability_score=0,
    estimated_input_tokens=10, total_score=0, difficulty="low", explanation="demo",
)
attempts = run_with_escalation(
    task="Explain DNS [mock:needs=strong]", analysis=analysis,
    start_tier="small", provider=MockModelProvider(),
)
for a in attempts:
    print(a.attempt_number, a.tier, "valid" if a.validation.valid else "FAILED", f"${a.estimated_cost:.6f}")
print(escalation_reasons(attempts))
print("total cost:", total_cost(attempts), "total latency:", total_latency(attempts))