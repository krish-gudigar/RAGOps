import pytest
from pydantic import ValidationError
from app.models.domain import TaskAnalysis


def make_analysis(**overrides):
    data = dict(
        task_type="coding", complexity_score=1, reasoning_score=1,
        context_score=0, constraints_score=1, reliability_score=2,
        estimated_input_tokens=50, total_score=5, difficulty="medium",
        explanation="test",
    )
    data.update(overrides)
    return TaskAnalysis(**data)


def test_valid_analysis():
    assert make_analysis().difficulty == "medium"


def test_score_out_of_range_rejected():
    with pytest.raises(ValidationError):
        make_analysis(complexity_score=3)