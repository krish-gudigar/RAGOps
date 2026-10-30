import json

import pytest

from app.models.domain import TaskAnalysis
from app.providers.mock_provider import MOCK_FAILURE_TEXT
from app.validation.base import make_result
from app.validation.code import CodeValidator
from app.validation.general import GeneralValidator
from app.validation.json_schema import StructuredOutputValidator
from app.validation.pipeline import ValidationExtras, build_validators, validate_response
from app.validation.requirements import FormatValidator, RequirementValidator


def make_analysis(task_type="general_question", difficulty="low"):
    return TaskAnalysis(
        task_type=task_type, complexity_score=0, reasoning_score=0,
        context_score=0, constraints_score=0, reliability_score=0,
        estimated_input_tokens=10, total_score=0, difficulty=difficulty,
        explanation="test",
    )


A = make_analysis()


def code_block(code):
    return f"Here you go:\n```python\n{code}\n```"


# ---------- make_result ----------
def test_result_with_errors_is_invalid_with_zero_score():
    r = make_result("x", ["bad"], [], "e")
    assert not r.valid and r.score == 0.0


def test_warnings_lower_the_score_but_stay_valid():
    r = make_result("x", [], ["w1", "w2"], "e")
    assert r.valid and r.score == pytest.approx(0.8)


# ---------- GeneralValidator ----------
def test_general_accepts_normal_answer():
    assert GeneralValidator().validate("t", "Paris is the capital of France.", A).valid


@pytest.mark.parametrize("text", ["", "   \n  "])
def test_general_rejects_empty(text):
    r = GeneralValidator().validate("t", text, A)
    assert not r.valid and "empty" in r.errors[0].lower()


def test_general_rejects_mock_failure_text():
    assert not GeneralValidator().validate("t", MOCK_FAILURE_TEXT, A).valid


def test_general_rejects_curly_apostrophe_refusal():
    assert not GeneralValidator().validate("t", "I\u2019m sorry, I can\u2019t help with that.", A).valid


def test_general_ignores_refusal_words_deep_inside_long_answer():
    text = "Photosynthesis is how plants make food. " * 10 + "I cannot help but admire it."
    assert GeneralValidator().validate("t", text, A).valid


def test_general_rejects_too_long():
    assert not GeneralValidator(max_chars=50).validate("t", "x" * 100, A).valid


def test_general_warns_on_very_short_answer():
    r = GeneralValidator().validate("t", "Paris", A)
    assert r.valid and r.warnings


# ---------- StructuredOutputValidator ----------
def test_json_valid_passes():
    assert StructuredOutputValidator().validate("t", '{"a": 1}', A).valid


def test_json_inside_code_fence_passes():
    assert StructuredOutputValidator().validate("t", '```json\n{"a": 1}\n```', A).valid


def test_json_invalid_reports_exact_position():
    r = StructuredOutputValidator().validate("t", '{"a": 1,', A)
    assert not r.valid
    assert "line 1" in r.errors[0] and "column" in r.errors[0]


def test_json_missing_required_fields():
    r = StructuredOutputValidator(["name", "age"]).validate("t", '{"name": "Asha"}', A)
    assert not r.valid and "age" in r.errors[0]


def test_json_required_fields_present():
    assert StructuredOutputValidator(["name"]).validate("t", '{"name": "Asha"}', A).valid


def test_json_array_cannot_have_required_fields():
    r = StructuredOutputValidator(["name"]).validate("t", "[1, 2]", A)
    assert not r.valid and "not an object" in r.errors[0]


# ---------- CodeValidator ----------
def test_code_valid_syntax_passes():
    assert CodeValidator().validate("t", code_block("def f(x):\n    return x"), A).valid


def test_code_syntax_error_reports_line():
    r = CodeValidator().validate("t", code_block("def f(x)\n    return x"), A)
    assert not r.valid and "line 1" in r.errors[0]


def test_code_without_block_fails_when_required():
    assert not CodeValidator(require_code_block=True).validate("t", "Just words.", A).valid


def test_code_without_block_only_warns_when_not_required():
    r = CodeValidator(require_code_block=False).validate("t", "Just words.", A)
    assert r.valid and r.warnings


TESTS = "from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
GOOD = code_block("def add(a, b):\n    return a + b")
WRONG = code_block("def add(a, b):\n    return a - b")


def test_tests_are_skipped_unless_execution_allowed():
    r = CodeValidator(test_code=TESTS).validate("t", WRONG, A)
    assert r.valid and r.validator_type == "syntax:python"
    assert "skipped" in r.warnings[0]


def test_tests_pass_when_execution_allowed():
    r = CodeValidator(test_code=TESTS, allow_execution=True).validate("t", GOOD, A)
    assert r.valid and r.validator_type == "test:pytest"


def test_tests_fail_for_wrong_code():
    r = CodeValidator(test_code=TESTS, allow_execution=True).validate("t", WRONG, A)
    assert not r.valid and "Tests failed" in r.errors[0]


def test_tests_time_out():
    loop = code_block("def add(a, b):\n    while True:\n        pass")
    r = CodeValidator(test_code=TESTS, allow_execution=True, timeout_seconds=2).validate("t", loop, A)
    assert not r.valid and "timed out" in r.errors[0]


# ---------- RequirementValidator ----------
def test_requirements_all_present_passes():
    v = RequirementValidator(required_keywords=["eco-friendly", "durable"])
    assert v.validate("t", "An Eco-Friendly and DURABLE bottle.", A).valid


def test_requirements_missing_keyword_fails():
    r = RequirementValidator(required_keywords=["eco-friendly", "durable"]).validate("t", "A durable bottle.", A)
    assert not r.valid and "eco-friendly" in r.errors[0]


def test_requirements_forbidden_keyword_fails():
    assert not RequirementValidator(forbidden_keywords=["!"]).validate("t", "Wow!", A).valid


def test_requirements_word_limit():
    v = RequirementValidator(max_words=3)
    assert v.validate("t", "one two three", A).valid
    assert not v.validate("t", "one two three four", A).valid


# ---------- FormatValidator ----------
def test_format_bullets():
    v = FormatValidator("bullets")
    assert v.validate("t", "- a\n- b", A).valid
    assert not v.validate("t", "- only one", A).valid


def test_format_numbered():
    v = FormatValidator("numbered")
    assert v.validate("t", "1. a\n2. b", A).valid
    assert not v.validate("t", "just text", A).valid


def test_format_headings():
    v = FormatValidator("headings")
    assert v.validate("t", "# Title\ntext", A).valid
    assert not v.validate("t", "no heading", A).valid


def test_format_json():
    v = FormatValidator("json")
    assert v.validate("t", '{"a": 1}', A).valid
    assert not v.validate("t", "{oops", A).valid


def test_format_unknown_raises():
    with pytest.raises(ValueError):
        FormatValidator("poetry")


# ---------- pipeline ----------
def test_pipeline_picks_validators_by_task_type():
    names = lambda t: [v.name for v in build_validators(make_analysis(t))]
    assert names("general_question") == ["heuristic:general"]
    assert names("structured_output") == ["heuristic:general", "syntax:json"]
    assert names("coding") == ["heuristic:general", "syntax:python"]


def test_pipeline_debugging_does_not_require_a_code_block():
    r = validate_response("t", "The bug is an off-by-one error in the loop.", make_analysis("debugging"))
    assert r.valid


def test_pipeline_coding_requires_a_code_block():
    r = validate_response("t", "You should write a function.", make_analysis("coding"))
    assert not r.valid


def test_pipeline_combines_errors_with_validator_names():
    r = validate_response("t", MOCK_FAILURE_TEXT, A)
    assert not r.valid and r.errors[0].startswith("[heuristic:general]")


def test_pipeline_catches_broken_json_for_structured_output():
    r = validate_response("t", '{"a": 1,', make_analysis("structured_output"))
    assert not r.valid and any("syntax:json" in e for e in r.errors)


def test_pipeline_passes_good_answer_and_states_its_limits():
    r = validate_response("t", json.dumps({"ok": True, "n": 1}), make_analysis("structured_output"))
    assert r.valid
    assert "do not prove" in r.explanation


def test_pipeline_extras_add_requirement_and_format_checks():
    extras = ValidationExtras(required_keywords=["python"], expected_format="bullets")
    r = validate_response("t", "- java\n- c", A, extras)
    assert not r.valid
    types = r.validator_type.split("+")
    assert "heuristic:requirements" in types and "format:output" in types