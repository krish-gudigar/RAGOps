"""HistoryRepository: saves every execution result to a local JSONL file.

One JSON object per line. Simple, readable, and easy to delete.

PRIVACY: this is a LOCAL EDUCATIONAL PROTOTYPE. By default the task text and
the model answers are saved so the history page can show them. Pass
store_task_text=False to save only scores, tiers, costs and timings. API keys
are never part of a result, so they are never stored.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from app.models.domain import TaskExecutionResult

NOT_STORED = "[not stored]"


class HistoryRecord(BaseModel):
    timestamp: str
    result: TaskExecutionResult


class HistoryRepository:
    def __init__(self, path: str | Path = "data/history.jsonl", store_task_text: bool = True):
        self.path = Path(path)
        self.store_task_text = store_task_text

    def add(self, result: TaskExecutionResult) -> HistoryRecord:
        to_save = result if self.store_task_text else self._redact(result)
        record = HistoryRecord(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"), result=to_save
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")
        return record

    def all_records(self) -> list[HistoryRecord]:
        """Oldest first. Lines that cannot be read are skipped."""
        if not self.path.exists():
            return []
        records = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(HistoryRecord.model_validate_json(line))
                except ValueError:
                    continue
        return records

    def recent(self, limit: int = 50) -> list[HistoryRecord]:
        """Newest first."""
        return list(reversed(self.all_records()))[:limit]

    def all_results(self) -> list[TaskExecutionResult]:
        return [r.result for r in self.all_records()]

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    @staticmethod
    def _redact(result: TaskExecutionResult) -> TaskExecutionResult:
        attempts = [a.model_copy(update={"response": NOT_STORED}) for a in result.attempts]
        return result.model_copy(
            update={"task": NOT_STORED, "final_response": NOT_STORED, "attempts": attempts}
        )