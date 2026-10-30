"""StructuredOutputValidator: is the response valid JSON with the right fields?

This is a SYNTAX check (plus an optional required-field check). It does not
check whether the values inside the JSON are correct.
"""

import json
import re

from app.models.domain import TaskAnalysis, ValidationResult
from app.validation.base import make_result

FENCE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


class StructuredOutputValidator:
    name = "syntax:json"

    def __init__(self, required_fields: list[str] | None = None):
        self.required_fields = required_fields or []

    def validate(self, task: str, response: str, analysis: TaskAnalysis) -> ValidationResult:
        errors: list[str] = []
        explanation = (
            "Syntax check: the response must parse as JSON"
            + (" and contain the required fields" if self.required_fields else "")
            + ". Values are not checked."
        )

        text = response.strip()
        fenced = FENCE.search(text)
        if fenced:
            text = fenced.group(1).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
            return make_result(self.name, errors, [], explanation)

        if self.required_fields:
            if not isinstance(data, dict):
                errors.append("Top-level JSON value is not an object, so required fields cannot be checked.")
            else:
                missing = [f for f in self.required_fields if f not in data]
                if missing:
                    errors.append(f"Missing required fields: {', '.join(missing)}")

        return make_result(self.name, errors, [], explanation)