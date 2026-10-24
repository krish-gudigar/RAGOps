"""Turn a strategy name (as sent by the API) into a router object."""

from app.routing.baselines import AlwaysSmallRouter, AlwaysStrongRouter, RandomRouter
from app.routing.rule_based import RuleBasedRouter

_ROUTERS = {
    "dynamic": RuleBasedRouter,
    "always_small": AlwaysSmallRouter,
    "always_strong": AlwaysStrongRouter,
    "random": RandomRouter,   # for evaluation only, not offered in the UI
}


def get_router(strategy: str):
    try:
        return _ROUTERS[strategy]()
    except KeyError:
        raise ValueError(
            f"Unknown strategy '{strategy}'. Available: {', '.join(_ROUTERS)}"
        ) from None