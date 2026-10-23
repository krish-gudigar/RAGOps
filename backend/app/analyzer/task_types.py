"""Rule-based task type detection.

Rules are checked in order and the FIRST type with a match wins, so
more specific types (debugging, coding) come before generic ones.
"""

import re

_RULES: list[tuple[str, list[str]]] = [
    ("debugging", [
        r"\bdebug(ging)?\b", r"\bstack ?trace\b", r"\btraceback\b", r"\bbug\b",
        r"\bexception\b", r"\bnot working\b",
        r"\bfix (the|this|my)\b[^.\n]{0,30}\b(error|bug|crash|issue)\b",
    ]),
    ("coding", [
        r"\b(write|create|implement|build|develop|design)\b[^.\n]{0,40}"
        r"\b(function|class|script|program|api|endpoint|algorithm|query|code|architecture)\b",
        r"\bimplement\b", r"\brefactor\b", r"\bdef \w+\(",
    ]),
    ("mathematics", [
        r"\bsolve\b", r"\bequation\b", r"\bcalculate\b", r"\bprobability\b",
        r"\bintegral\b", r"\bderivative\b", r"\d+\s*%", r"\b\d+(\.\d+)?\s*[+*/^]\s*\d+",
    ]),
    ("summarization", [
        r"\bsummari[sz]e\b", r"\bsummary\b", r"\btl;?dr\b", r"\bshorten\b", r"\bcondense\b",
    ]),
    ("extraction", [
        r"\bextract\b", r"\bpull out\b", r"\blist all\b", r"\bfind all\b", r"\bidentify all\b",
    ]),
    ("structured_output", [
        r"\bjson\b", r"\byaml\b", r"\bcsv\b", r"\bxml\b", r"\bschema\b", r"\bkey-value\b",
    ]),
    ("planning", [
        r"\bplan\b", r"\bschedule\b", r"\broadmap\b", r"\bitinerary\b", r"\bstrategy\b",
    ]),
    ("transformation", [
        r"\btranslate\b", r"\brewrite\b", r"\bparaphrase\b", r"\bconvert\b",
        r"\bproofread\b", r"\breword\b", r"\b(upper|lower)case\b", r"\bgrammar\b",
    ]),
    ("reasoning", [
        r"\bwhy\b", r"\bcompare\b", r"\btrade-?offs?\b", r"\bpros and cons\b",
        r"\banaly[sz]e\b", r"\bevaluate\b", r"\bjustify\b", r"\bexplain\b",
    ]),
    ("general_question", [
        r"^\s*(what|who|when|where|which|how)\b", r"\?\s*$",
    ]),
]


def detect_task_type(task: str) -> tuple[str, list[str]]:
    """Return (task_type, signals). Signals show which words triggered the type."""
    text = task.lower()
    for task_type, patterns in _RULES:
        hits = [m.group(0) for p in patterns if (m := re.search(p, text))]
        if hits:
            return task_type, [f"type={task_type}: matched '{h}'" for h in hits]
    return "unknown", []