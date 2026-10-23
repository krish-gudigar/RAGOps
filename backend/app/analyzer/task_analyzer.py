"""TaskAnalyzer: turns a task into five transparent 0-2 scores.

Every score comes from simple, readable rules, so every decision can be
explained in the UI. These are heuristics, NOT a measure of true difficulty.
"""

import re

from app.analyzer.task_types import detect_task_type
from app.analyzer.token_estimator import estimate_tokens
from app.config import Thresholds
from app.models.domain import TaskAnalysis

# Starting scores by task type (a keyword boost can raise them, up to 2).
COMPLEXITY_BY_TYPE = {
    "transformation": 0, "general_question": 0, "unknown": 0,
    "summarization": 1, "extraction": 1, "structured_output": 1, "coding": 1,
    "mathematics": 1, "planning": 1, "reasoning": 1, "debugging": 2,
}
REASONING_BY_TYPE = {
    "transformation": 0, "general_question": 0, "unknown": 0, "summarization": 0,
    "extraction": 0, "structured_output": 0, "coding": 1, "planning": 1,
    "reasoning": 1, "mathematics": 2, "debugging": 2,
}
RELIABILITY_BY_TYPE = {
    "transformation": 0,
    "general_question": 1, "unknown": 1, "summarization": 1, "extraction": 1,
    "planning": 1, "reasoning": 1,
    "coding": 2, "debugging": 2, "structured_output": 2, "mathematics": 2,
}

HARD_TASK_PATTERNS = [
    r"\barchitecture\b", r"\bscalable\b", r"\bdistributed\b", r"\brefactor\b",
    r"\bend-to-end\b", r"\bmulti-?step\b", r"\brace condition\b",
    r"\bconcurren\w*\b", r"\bmicroservices?\b",
]
STRONG_REASONING_PATTERNS = [
    r"step[- ]by[- ]step", r"\btrade-?offs?\b", r"\bmulti-?step\b", r"\bprove\b",
    r"\bjustify\b", r"\bderive\b", r"\boptimi[sz]e\b", r"\broot cause\b",
]
MILD_REASONING_PATTERNS = [
    r"\bwhy\b", r"\bcompare\b", r"\bexplain\b", r"\bpros and cons\b",
    r"\bdifference between\b",
]
LARGE_CONTEXT_PATTERNS = [
    r"\b(multiple|several|many) (files|modules|documents)\b",
    r"\bentire (codebase|repo|repository)\b", r"\bconversation history\b",
    r"\blong document\b",
]
HIGH_STAKES_PATTERNS = [
    r"\bproduction\b", r"\bmedical\b", r"\blegal\b", r"\bfinancial\b",
    r"\bsecurity\b", r"\bmust be (correct|accurate)\b", r"\bcritical\b",
]
# Each NAME counts once, however many times it appears.
CONSTRAINT_PATTERNS = {
    "length limit": r"\b(under|at most|no more than|maximum|max|within|exactly)\s+\d+\s*"
                    r"(words?|sentences?|characters?|lines?|bullets?|paragraphs?)\b",
    "output format": r"\b(json|yaml|csv|markdown|table|bullet points?|bulleted|headings?|numbered list)\b",
    "required behaviour": r"\b(must|required|need to|has to)\b",
    "prohibition": r"\b(do not|don't|never|without using|avoid|must not|should not)\b",
    "exactness": r"\b(only|exactly)\b",
    "edge cases": r"\bedge cases?\b",
    "tests/docs": r"\b(unit tests?|type hints?|docstrings?|pytest)\b",
    "compatibility": r"\b(compatible|compatibility|python ?3\.\d+)\b",
}


def _find(patterns: list[str], text: str) -> list[str]:
    return [m.group(0) for p in patterns if (m := re.search(p, text))]


def classify_difficulty(total_score: int, thresholds: Thresholds) -> str:
    if total_score <= thresholds.low_max:
        return "low"
    if total_score <= thresholds.medium_max:
        return "medium"
    return "high"


class TaskAnalyzer:
    def __init__(self, thresholds: Thresholds | None = None):
        self.thresholds = thresholds or Thresholds()

    def analyze(self, task: str) -> TaskAnalysis:
        text = task.lower()
        task_type, signals = detect_task_type(task)

        # A. Complexity
        complexity = COMPLEXITY_BY_TYPE.get(task_type, 0)
        hard = _find(HARD_TASK_PATTERNS, text)
        if hard:
            complexity = min(2, complexity + 1)
            signals += [f"complexity: hard-task word '{h}'" for h in hard]

        # B. Reasoning
        reasoning = REASONING_BY_TYPE.get(task_type, 0)
        strong = _find(STRONG_REASONING_PATTERNS, text)
        mild = _find(MILD_REASONING_PATTERNS, text)
        if strong:
            reasoning = min(2, reasoning + 1)
            signals += [f"reasoning: strong cue '{s}'" for s in strong]
        elif mild:
            reasoning = max(reasoning, 1)
            signals += [f"reasoning: mild cue '{m}'" for m in mild]

        # C. Context size (token estimate, plus words that imply big context)
        tokens = estimate_tokens(task)
        if tokens >= self.thresholds.long_context_tokens:
            context = 2
        elif tokens >= self.thresholds.medium_context_tokens:
            context = 1
        else:
            context = 0
        big = _find(LARGE_CONTEXT_PATTERNS, text)
        if big:
            context = 2
            signals += [f"context: '{b}'" for b in big]

        # D. Constraints
        constraints = [name for name, p in CONSTRAINT_PATTERNS.items() if re.search(p, text)]
        if not constraints:
            constraints_score = 0
        elif len(constraints) <= 2:
            constraints_score = 1
        else:
            constraints_score = 2

        # E. Reliability
        reliability = RELIABILITY_BY_TYPE.get(task_type, 1)
        stakes = _find(HIGH_STAKES_PATTERNS, text)
        if stakes:
            reliability = 2
            signals += [f"reliability: high-stakes word '{s}'" for s in stakes]

        total = complexity + reasoning + context + constraints_score + reliability
        difficulty = classify_difficulty(total, self.thresholds)

        explanation = (
            f"Detected task type '{task_type}'. Scores: complexity {complexity}, "
            f"reasoning {reasoning}, context {context} (~{tokens} tokens), "
            f"constraints {constraints_score}, reliability {reliability}. "
            f"Total {total}/10 -> {difficulty} difficulty (heuristic estimate)."
        )

        return TaskAnalysis(
            task_type=task_type,
            complexity_score=complexity,
            reasoning_score=reasoning,
            context_score=context,
            constraints_score=constraints_score,
            reliability_score=reliability,
            estimated_input_tokens=tokens,
            detected_constraints=constraints,
            detected_signals=signals,
            total_score=total,
            difficulty=difficulty,
            explanation=explanation,
        )