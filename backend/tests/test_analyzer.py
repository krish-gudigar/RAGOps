import pytest

from app.analyzer.task_analyzer import TaskAnalyzer, classify_difficulty
from app.analyzer.task_types import detect_task_type
from app.analyzer.token_estimator import estimate_tokens
from app.config import Thresholds

analyzer = TaskAnalyzer()


# ---------- token estimator ----------
def test_empty_text_is_zero():
    assert estimate_tokens("") == 0


def test_short_text_is_positive():
    assert estimate_tokens("Hello world") > 0


def test_longer_text_has_more_tokens():
    assert estimate_tokens("Hello world. " * 100) > estimate_tokens("Hello world")


def test_fallback_when_tiktoken_unavailable(monkeypatch):
    monkeypatch.setattr("app.analyzer.token_estimator._get_encoder", lambda: None)
    assert estimate_tokens("a" * 400) == 100
    assert estimate_tokens("hi") == 1


# ---------- task type detection ----------
@pytest.mark.parametrize("task, expected", [
    ("Translate this sentence to Spanish.", "transformation"),
    ("Summarize this article in 3 sentences.", "summarization"),
    ("Extract all email addresses from the text below.", "extraction"),
    ("Return the user's name and age as JSON.", "structured_output"),
    ("Write a Python function that checks if a number is prime.", "coding"),
    ("Why does my code crash with a traceback?", "debugging"),
    ("Solve 2x + 3 = 11.", "mathematics"),
    ("Plan a 3-day study schedule for my exams.", "planning"),
    ("Compare REST and GraphQL and explain the trade-offs.", "reasoning"),
    ("What is the capital of France?", "general_question"),
    ("asdf qwerty", "unknown"),
])
def test_task_type_detection(task, expected):
    assert detect_task_type(task)[0] == expected


# ---------- scoring ----------
def test_simple_transformation_is_low():
    a = analyzer.analyze("Translate 'Good morning' to French.")
    assert a.task_type == "transformation"
    assert a.total_score <= 3
    assert a.difficulty == "low"


def test_simple_question_is_low():
    a = analyzer.analyze("What is the capital of France?")
    assert a.task_type == "general_question"
    assert a.difficulty == "low"


def test_complex_debugging_is_high():
    task = (
        "Debug a race condition across multiple files in our Python service. "
        "The stack trace points to the cache layer. Fix the bug, keep it "
        "compatible with Python 3.8, add unit tests, handle edge cases, and "
        "explain the root cause step by step."
    )
    a = analyzer.analyze(task)
    assert a.task_type == "debugging"
    assert a.total_score >= 8
    assert a.difficulty == "high"


def test_long_context_raises_context_score():
    short = analyzer.analyze("Translate the following text: hello")
    medium = analyzer.analyze("Translate the following text: " + "word " * 400)
    long = analyzer.analyze("Translate the following text: " + "word " * 2000)
    assert short.context_score == 0
    assert medium.context_score == 1
    assert long.context_score == 2


def test_length_alone_does_not_make_task_high():
    a = analyzer.analyze("Translate the following text: " + "word " * 2000)
    assert a.context_score == 2
    assert a.difficulty == "low"


def test_multiple_constraints_raise_constraints_score():
    plain = analyzer.analyze("Write a product description.")
    strict = analyzer.analyze(
        "Write a product description in exactly 50 words. It must mention "
        "'eco-friendly' and 'durable'. Do not use exclamation marks. "
        "Format it as a bulleted list."
    )
    assert plain.constraints_score == 0
    assert strict.constraints_score == 2
    assert len(strict.detected_constraints) >= 3


def test_single_constraint_scores_one():
    a = analyzer.analyze("Summarize this in under 50 words.")
    assert a.constraints_score == 1


def test_signals_and_explanation_are_exposed():
    a = analyzer.analyze("Compare REST and GraphQL and explain the trade-offs.")
    assert a.detected_signals
    assert "Total" in a.explanation


# ---------- thresholds ----------
def test_default_thresholds_classify_correctly():
    t = Thresholds()
    assert classify_difficulty(0, t) == "low"
    assert classify_difficulty(3, t) == "low"
    assert classify_difficulty(4, t) == "medium"
    assert classify_difficulty(7, t) == "medium"
    assert classify_difficulty(8, t) == "high"
    assert classify_difficulty(10, t) == "high"


def test_custom_thresholds_change_classification():
    t = Thresholds(low_max=2, medium_max=5)
    assert classify_difficulty(3, t) == "medium"
    assert classify_difficulty(6, t) == "high"