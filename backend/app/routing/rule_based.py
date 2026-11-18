"""The explainable rule-based router.

Rule 1: difficulty decides the tier (low -> small, medium -> medium, high -> strong).
Rule 2 (safety): if reliability score is 2, the small tier is raised to medium.
Both rules are written into the `reason` text so the decision can be explained.
"""

from app.config import Settings
from app.models.domain import RoutingDecision, TaskAnalysis
from app.routing.base import build_decision
from app.routing.expert_gate import ExpertDecision

TIER_BY_DIFFICULTY = {"low": "small", "medium": "medium", "high": "strong"}


class RuleBasedRouter:
    name = "dynamic"

    def route(
        self, analysis: TaskAnalysis, settings: Settings,
        expert_decision: ExpertDecision | None = None,
    ) -> RoutingDecision:
        tier = TIER_BY_DIFFICULTY[analysis.difficulty]
        reason = (
            f"Total score {analysis.total_score}/10 means '{analysis.difficulty}' "
            f"difficulty, so the {tier} tier was chosen."
        )

        if (
            settings.raise_small_for_high_reliability
            and tier == "small"
            and analysis.reliability_score == 2
        ):
            tier = "medium"
            reason += (
                " Safety rule: reliability score is 2 (correctness matters), "
                "so the tier was raised from small to medium."
            )

        # Confidence stays None: this router has no probability to report.
        return build_decision(
            tier, self.name, reason, analysis, settings, confidence=None,
            expert_decision=expert_decision,
        )