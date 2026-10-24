"""Baseline routers used for comparison. They ignore the task analysis."""

import random

from app.config import TIERS, Settings
from app.models.domain import RoutingDecision, TaskAnalysis
from app.routing.base import build_decision


class AlwaysSmallRouter:
    name = "always_small"

    def route(self, analysis: TaskAnalysis, settings: Settings) -> RoutingDecision:
        return build_decision(
            "small", self.name, "Baseline: always use the small model.", analysis, settings
        )


class AlwaysStrongRouter:
    name = "always_strong"

    def route(self, analysis: TaskAnalysis, settings: Settings) -> RoutingDecision:
        return build_decision(
            "strong", self.name, "Baseline: always use the strong model.", analysis, settings
        )


class RandomRouter:
    """Picks a tier at random (seeded, so results are reproducible).

    This is a sanity-check baseline: a real router should beat random choice.
    A cost-matched version is added in the evaluation phase.
    """

    name = "random"

    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)

    def route(self, analysis: TaskAnalysis, settings: Settings) -> RoutingDecision:
        tier = self._rng.choice(TIERS)
        return build_decision(
            tier, self.name, "Baseline: tier chosen at random.", analysis, settings
        )