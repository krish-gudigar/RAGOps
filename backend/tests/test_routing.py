import pytest

from app.analyzer.task_analyzer import TaskAnalyzer
from app.config import Expert, Settings, TASK_TYPE_TO_EXPERT
from app.models.domain import TaskAnalysis
from app.routing.baselines import AlwaysSmallRouter, AlwaysStrongRouter, RandomRouter
from app.routing.factory import get_router
from app.routing.rule_based import RuleBasedRouter
from app.routing.expert_gate import ExpertDecision

settings = Settings()


def make_analysis(difficulty="medium", total=5, reliability=1, tokens=100):
    return TaskAnalysis(
        task_type="coding", complexity_score=1, reasoning_score=1,
        context_score=0, constraints_score=0, reliability_score=reliability,
        estimated_input_tokens=tokens, total_score=total, difficulty=difficulty,
        explanation="test",
    )


# ---------- cost ----------
def test_estimate_cost_uses_configured_prices():
    # strong: (1000 * 3.00 + 1000 * 15.00) / 1,000,000 = 0.018
    assert settings.estimate_cost("strong", 1000, 1000) == pytest.approx(0.018)
    # small: (1000 * 0.10 + 1000 * 0.40) / 1,000,000 = 0.0005
    assert settings.estimate_cost("small", 1000, 1000) == pytest.approx(0.0005)


def test_strong_costs_more_than_small():
    assert settings.estimate_cost("strong", 500, 200) > settings.estimate_cost("small", 500, 200)


def test_model_names_can_come_from_environment(monkeypatch):
    monkeypatch.setenv("SMALL_MODEL", "llama3.2:1b")
    assert Settings().model_for("small").name == "llama3.2:1b"


@pytest.mark.parametrize("task_type, expert", [
    ("debugging", Expert.CODING),
    ("coding", Expert.CODING),
    ("mathematics", Expert.REASONING),
    ("reasoning", Expert.REASONING),
    ("planning", Expert.REASONING),
    ("summarization", Expert.GENERAL),
    ("extraction", Expert.GENERAL),
    ("structured_output", Expert.GENERAL),
    ("transformation", Expert.GENERAL),
    ("general_question", Expert.GENERAL),
    ("unknown", Expert.GENERAL),
])
def test_task_types_map_to_the_configured_expert(task_type, expert):
    assert TASK_TYPE_TO_EXPERT[task_type] == expert


def test_expert_model_prices_default_to_the_general_tier_prices():
    settings = Settings()
    coding_model = settings.model_for("medium", Expert.CODING)
    general_model = settings.model_for("medium")
    assert coding_model.name == settings.expert_models[Expert.CODING]["medium"]
    assert coding_model.price_in_per_1m == general_model.price_in_per_1m
    assert coding_model.price_out_per_1m == general_model.price_out_per_1m
    assert all(settings.expert_models[Expert.REASONING][tier] is None for tier in settings.models)


def test_expert_decision_does_not_change_rule_based_tier():
    analysis = make_analysis(difficulty="high", total=9, reliability=1)
    expert = ExpertDecision(
        expert=Expert.CODING, stage="regex", reason="coding detected by regex"
    )
    decision = RuleBasedRouter().route(analysis, settings, expert)
    assert decision.selected_tier == "strong"
    assert decision.expert == Expert.CODING
    assert decision.model_name == settings.expert_models[Expert.CODING]["strong"]
    assert decision.gate_stage == "regex"
    assert "score 9/10" in decision.reason


def test_expert_model_missing_at_selected_tier_falls_back_to_general():
    analysis = make_analysis(difficulty="medium", total=5, reliability=1)
    expert = ExpertDecision(
        expert=Expert.REASONING, stage="embedding", reason="matched reasoning example"
    )
    decision = RuleBasedRouter().route(analysis, settings, expert)
    assert decision.selected_tier == "medium"
    assert decision.model_name == settings.models["medium"].name
    assert decision.expert == Expert.GENERAL
    assert "No reasoning model configured" in decision.fallback_reason
    assert "using the general model" in decision.reason


def test_disabled_expert_routing_preserves_legacy_decision_reason():
    analysis = make_analysis(difficulty="low", total=2, reliability=1)
    decision = RuleBasedRouter().route(analysis, settings)
    assert decision.reason == (
        "Total score 2/10 means 'low' difficulty, so the small tier was chosen."
    )
    assert decision.expert == Expert.GENERAL
    assert decision.gate_stage is None


# ---------- baselines ----------
def test_always_small():
    d = AlwaysSmallRouter().route(make_analysis(difficulty="high", total=9), settings)
    assert d.selected_tier == "small"
    assert d.strategy == "always_small"


def test_always_strong():
    d = AlwaysStrongRouter().route(make_analysis(difficulty="low", total=1), settings)
    assert d.selected_tier == "strong"
    assert d.strategy == "always_strong"


def test_random_router_is_reproducible_with_same_seed():
    a = [RandomRouter(seed=1).route(make_analysis(), settings).selected_tier for _ in range(1)]
    r1, r2 = RandomRouter(seed=7), RandomRouter(seed=7)
    seq1 = [r1.route(make_analysis(), settings).selected_tier for _ in range(20)]
    seq2 = [r2.route(make_analysis(), settings).selected_tier for _ in range(20)]
    assert seq1 == seq2
    assert set(seq1) <= {"small", "medium", "strong"}
    assert len(set(seq1)) > 1  # not stuck on a single tier


# ---------- rule-based ----------
@pytest.mark.parametrize("difficulty, total, tier", [
    ("low", 2, "small"),
    ("medium", 5, "medium"),
    ("high", 9, "strong"),
])
def test_difficulty_maps_to_tier(difficulty, total, tier):
    d = RuleBasedRouter().route(make_analysis(difficulty, total), settings)
    assert d.selected_tier == tier
    assert d.strategy == "dynamic"
    assert d.confidence is None


def test_high_reliability_raises_small_to_medium():
    analysis = make_analysis(difficulty="low", total=2, reliability=2)
    d = RuleBasedRouter().route(analysis, settings)
    assert d.selected_tier == "medium"
    assert "Safety rule" in d.reason


def test_safety_rule_can_be_turned_off():
    s = Settings(raise_small_for_high_reliability=False)
    analysis = make_analysis(difficulty="low", total=2, reliability=2)
    assert RuleBasedRouter().route(analysis, s).selected_tier == "small"


def test_safety_rule_never_lowers_a_tier():
    analysis = make_analysis(difficulty="high", total=9, reliability=2)
    assert RuleBasedRouter().route(analysis, settings).selected_tier == "strong"


def test_decision_contains_model_cost_and_latency():
    d = RuleBasedRouter().route(make_analysis("high", 9, tokens=1000), settings)
    assert d.selected_model == settings.model_for("strong").name
    assert d.estimated_cost > 0
    assert d.expected_latency_ms == settings.model_for("strong").expected_latency_ms
    assert d.reason


# ---------- analyzer + router together ----------
def test_simple_task_goes_small_and_hard_task_goes_strong():
    analyzer = TaskAnalyzer()
    router = RuleBasedRouter()
    simple = analyzer.analyze("Translate 'Good morning' to French.")
    hard = analyzer.analyze(
        "Debug a race condition across multiple files in our Python service. "
        "The stack trace points to the cache layer. Fix the bug, keep it "
        "compatible with Python 3.8, add unit tests, handle edge cases, and "
        "explain the root cause step by step."
    )
    assert router.route(simple, settings).selected_tier == "small"
    assert router.route(hard, settings).selected_tier == "strong"


# ---------- factory ----------
def test_factory_returns_correct_routers():
    assert get_router("dynamic").name == "dynamic"
    assert get_router("expert_pool").name == "dynamic"
    assert get_router("always_small").name == "always_small"
    assert get_router("always_strong").name == "always_strong"


def test_factory_rejects_unknown_strategy():
    with pytest.raises(ValueError):
        get_router("magic")