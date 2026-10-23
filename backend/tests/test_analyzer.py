from app.analyzer.token_estimator import estimate_tokens


def test_empty_text_is_zero():
    assert estimate_tokens("") == 0


def test_short_text_is_positive():
    assert estimate_tokens("Hello world") > 0


def test_longer_text_has_more_tokens():
    short = "Hello world"
    long = "Hello world. " * 100
    assert estimate_tokens(long) > estimate_tokens(short)


def test_fallback_when_tiktoken_unavailable(monkeypatch):
    # Force the "no tiktoken" path so the fallback is tested too.
    monkeypatch.setattr("app.analyzer.token_estimator._get_encoder", lambda: None)
    assert estimate_tokens("a" * 400) == 100
    assert estimate_tokens("hi") == 1  # never 0 for non-empty text