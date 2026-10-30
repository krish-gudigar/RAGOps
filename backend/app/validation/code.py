"""CodeValidator: checks Python code in a response.

Two levels:
  1. SYNTAX check (always): every ```python block must parse.
  2. TEST check (optional): run your pytest tests against the code.

!!! SECURITY WARNING (LOCAL DEMO ONLY) !!!
Running tests EXECUTES code written by an AI model on YOUR computer. That code
could do anything your user account can do. Execution is therefore OFF by
default and only happens when you pass allow_execution=True. It runs in a
temporary folder with a timeout and a reduced environment, but this is NOT a
real sandbox. Never enable it on a shared or production machine.

How tests are run: the response's code is saved as solution.py, your tests as
test_solution.py (use `from solution import ...`), then `pytest` is run.
"""

import ast
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from app.models.domain import TaskAnalysis, ValidationResult
from app.validation.base import make_result

CODE_BLOCK = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
SAFE_ENV_KEYS = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")


class CodeValidator:
    name = "syntax:python"

    def __init__(
        self,
        require_code_block: bool = True,
        test_code: str | None = None,
        allow_execution: bool = False,
        timeout_seconds: int = 10,
    ):
        self.require_code_block = require_code_block
        self.test_code = test_code
        self.allow_execution = allow_execution
        self.timeout_seconds = timeout_seconds

    def validate(self, task: str, response: str, analysis: TaskAnalysis) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        explanation = "Syntax check: Python code blocks must parse. Does not prove the code is correct."

        blocks = CODE_BLOCK.findall(response)
        if not blocks:
            message = "No Python code block found (expected a ```python block)."
            (errors if self.require_code_block else warnings).append(message)
            return make_result(self.name, errors, warnings, explanation)

        for i, block in enumerate(blocks, start=1):
            try:
                ast.parse(block)
            except SyntaxError as exc:
                errors.append(f"Syntax error in code block {i}, line {exc.lineno}: {exc.msg}")
        if errors:
            return make_result(self.name, errors, warnings, explanation)

        validator_type = self.name
        if self.test_code:
            if not self.allow_execution:
                warnings.append("Tests were provided but code execution is disabled, so they were skipped.")
            else:
                validator_type = "test:pytest"
                explanation = "Test check: the code was run against your pytest tests. Only as good as those tests."
                errors += self._run_tests("\n\n".join(blocks))

        return make_result(validator_type, errors, warnings, explanation)

    def _run_tests(self, code: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "solution.py").write_text(code, encoding="utf-8")
            Path(tmp, "test_solution.py").write_text(self.test_code, encoding="utf-8")
            env = {k: os.environ[k] for k in SAFE_ENV_KEYS if k in os.environ}
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            command = [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"]
            try:
                done = subprocess.run(
                    command, cwd=tmp, env=env, capture_output=True, text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return [f"Tests timed out after {self.timeout_seconds} seconds."]

        if done.returncode == 0:
            return []
        tail = (done.stdout + done.stderr).strip().splitlines()[-5:]
        return ["Tests failed: " + " | ".join(tail)]