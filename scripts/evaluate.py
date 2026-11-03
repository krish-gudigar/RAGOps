"""RouteWise evaluation: run a fixed task set through all three strategies.

Run from the project root:
    python scripts/evaluate.py                  # all 30 tasks, all strategies
    python scripts/evaluate.py --limit 3        # quick dry run (first 3 tasks)
    python scripts/evaluate.py --summarize data/eval/results_XXXX.csv

Results are written to data/eval/ after every single run, so Ctrl+C does not lose work.
Uses PROVIDER_MODE from .env. Numbers from mock mode are NOT real results.
"""

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.execution.orchestrator import Orchestrator  # noqa: E402
from app.models.requests import TaskRequest  # noqa: E402
from app.providers.errors import ProviderError  # noqa: E402
from app.providers.factory import get_provider  # noqa: E402

STRATEGIES = ["always_small", "always_strong", "dynamic"]

TASKS = [
    # ---------- easy ----------
    ("E01", "easy", "Translate 'Where is the library?' to French."),
    ("E02", "easy", "Translate 'Good morning' to Spanish."),
    ("E03", "easy", "What is the capital of Japan?"),
    ("E04", "easy", "Write a Python function that reverses a string."),
    ("E05", "easy", "Return a JSON object with the keys name and age for a made-up person."),
    ("E06", "easy", "Summarize in one sentence: The Moon orbits the Earth about every 27 days and causes the tides."),
    ("E07", "easy", "Convert 100 degrees Celsius to Fahrenheit."),
    ("E08", "easy", "Write a Python function that returns the sum of a list of numbers."),
    ("E09", "easy", "List three primary colors."),
    ("E10", "easy", "Rewrite this sentence in formal English: 'gonna be late, sorry'."),
    # ---------- medium ----------
    ("M01", "medium", "Explain how DNS works in a short paragraph."),
    ("M02", "medium", "Write a Python function that checks whether a string is a palindrome, ignoring case and punctuation."),
    ("M03", "medium", "Return a JSON object describing a book with the keys title, author, year, and genres (a list of strings)."),
    ("M04", "medium", "Explain the difference between a list and a tuple in Python, with an example."),
    ("M05", "medium", "Write a Python function that counts word frequencies in a text and returns a dictionary."),
    ("M06", "medium", "Explain why the sky is blue in three short sentences."),
    ("M07", "medium", "Compare TCP and UDP and give at least three differences."),
    ("M08", "medium", "Write a SQL query that returns the top 3 customers by total order amount from the tables customers and orders."),
    ("M09", "medium", "Explain what overfitting is in machine learning and give two ways to reduce it."),
    ("M10", "medium", "Write a Python function that merges two sorted lists into one sorted list without using sort()."),
    # ---------- hard ----------
    ("H01", "hard", "Write a Python function that checks whether a Sudoku board is valid, and explain your approach step by step."),
    ("H02", "hard", "Debug a race condition across multiple files in our Python service. The stack trace points to the cache layer. Fix the bug, keep it compatible with Python 3.8, add unit tests, handle edge cases, and explain the root cause step by step."),
    ("H03", "hard", "Design a REST API for a library system with endpoints for books, members and loans. Include JSON examples, handle edge cases, and explain the trade-offs step by step."),
    ("H04", "hard", "Implement an LRU cache in Python with O(1) get and put, add unit tests, and explain the time complexity."),
    ("H05", "hard", "Explain step by step how the Raft consensus algorithm elects a leader and what happens during a network partition."),
    ("H06", "hard", "Write a Python function that finds the longest palindromic substring. Keep it under 25 lines, handle edge cases, and explain the complexity."),
    ("H07", "hard", "Compare three database designs for a high-traffic chat application and recommend one with reasons and risks. Think carefully, step by step."),
    ("H08", "hard", "Write a Python script that parses a CSV file of sales, computes monthly totals, handles missing values and malformed rows, and includes unit tests."),
    ("H09", "hard", "Return a JSON object with the keys plan, risks and timeline for migrating a monolith to microservices. Both risks and timeline must be lists of at least three items."),
    ("H10", "hard", "Prove that the square root of 2 is irrational and explain each step carefully."),
]

FIELDS = ["task_id", "level", "strategy", "final_tier", "final_model", "success",
          "validated", "attempts", "escalated", "latency_ms", "cost",
          "score", "difficulty", "error", "task", "answer"]


def run_one(orch, task_id, level, prompt, strategy):
    row = {"task_id": task_id, "level": level, "strategy": strategy, "task": prompt,
           "final_tier": "", "final_model": "", "success": 0, "validated": 0,
           "attempts": 0, "escalated": 0, "latency_ms": 0, "cost": 0.0,
           "score": "", "difficulty": "", "error": "", "answer": ""}
    request = TaskRequest(task=prompt, strategy=strategy,
                          enable_validation=True,
                          enable_escalation=(strategy == "dynamic"),
                          max_escalations=2)
    try:
        result = orch.execute(request)
    except ProviderError as error:
        row["error"] = str(error)
        return row
    last = result.attempts[-1]
    row.update(
        final_tier=result.final_tier,
        final_model=last.model,
        success=int(bool(result.success)),
        validated=int(last.validation is not None),
        attempts=len(result.attempts),
        escalated=int(len(result.attempts) > 1),
        latency_ms=result.total_latency_ms,
        cost=result.total_estimated_cost,
        score=result.analysis.total_score,
        difficulty=result.analysis.difficulty,
        answer=result.final_response,
    )
    return row


def load_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for key in ("success", "validated", "attempts", "escalated", "latency_ms"):
                r[key] = int(float(r[key] or 0))
            r["cost"] = float(r["cost"] or 0)
            rows.append(r)
    return rows


def summarize(rows):
    good = [r for r in rows if not r["error"]]
    errors = len(rows) - len(good)
    lines = []
    out = lines.append

    out("OVERALL (per strategy)")
    out(f"{'strategy':<14}{'runs':>5}{'success':>9}{'escalated':>11}"
        f"{'avg time s':>12}{'avg cost $':>12}{'total cost $':>14}")
    stats = {}
    for s in STRATEGIES:
        rs = [r for r in good if r["strategy"] == s]
        if not rs:
            continue
        n = len(rs)
        stats[s] = {
            "n": n,
            "success": sum(r["success"] for r in rs) / n,
            "escalated": sum(r["escalated"] for r in rs) / n,
            "latency": sum(r["latency_ms"] for r in rs) / n / 1000,
            "cost": sum(r["cost"] for r in rs) / n,
            "total": sum(r["cost"] for r in rs),
        }
        st = stats[s]
        out(f"{s:<14}{n:>5}{st['success']:>9.0%}{st['escalated']:>11.0%}"
            f"{st['latency']:>12.1f}{st['cost']:>12.6f}{st['total']:>14.6f}")

    out("")
    out("SUCCESS RATE BY TASK LEVEL")
    out(f"{'strategy':<14}{'easy':>8}{'medium':>8}{'hard':>8}")
    for s in STRATEGIES:
        cells = []
        for level in ("easy", "medium", "hard"):
            rs = [r for r in good if r["strategy"] == s and r["level"] == level]
            cells.append(f"{sum(r['success'] for r in rs) / len(rs):.0%}" if rs else "n/a")
        out(f"{s:<14}{cells[0]:>8}{cells[1]:>8}{cells[2]:>8}")

    dyn = [r for r in good if r["strategy"] == "dynamic"]
    if dyn:
        out("")
        out("DYNAMIC: final tier used  " + str(dict(Counter(r["final_tier"] for r in dyn))))

    if "dynamic" in stats and "always_strong" in stats:
        d, a = stats["dynamic"], stats["always_strong"]
        out("")
        out("DYNAMIC vs ALWAYS_STRONG (this task set only)")
        if a["total"] > 0:
            out(f"  estimated cost: {(d['total'] / a['total'] - 1):+.0%}")
        if a["latency"] > 0:
            out(f"  average time:   {(d['latency'] / a['latency'] - 1):+.0%}")
        out(f"  success rate:   {(d['success'] - a['success']) * 100:+.0f} percentage points")

    out("")
    out(f"Runs with provider errors (excluded above): {errors}")
    out("Success = final answer passed the validators. It is NOT proof of correctness.")
    out("Costs are estimates from the configured prices. One run per task, one machine.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="only run the first N tasks")
    parser.add_argument("--summarize", help="print a summary of an existing results CSV and exit")
    args = parser.parse_args()

    if args.summarize:
        print(summarize(load_rows(args.summarize)))
        return

    settings = Settings()
    provider = get_provider(settings=settings)
    info = provider.get_model_info()
    orch = Orchestrator(provider=provider, settings=settings, repository=None)

    tasks = TASKS[: args.limit] if args.limit else TASKS
    out_dir = ROOT / "data" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"results_{info.mode}_{stamp}.csv"

    print(f"Provider: {info.provider} ({info.mode} mode) | models: {info.models}")
    if info.mode == "mock":
        print("WARNING: mock mode. These numbers are simulated, not real results.")
    print(f"{len(tasks)} tasks x {len(STRATEGIES)} strategies = {len(tasks) * len(STRATEGIES)} runs")
    print(f"Saving to {csv_path}\n")

    rows = []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        total = len(tasks) * len(STRATEGIES)
        count = 0
        try:
            for task_id, level, prompt in tasks:
                for strategy in STRATEGIES:
                    count += 1
                    row = run_one(orch, task_id, level, prompt, strategy)
                    writer.writerow(row)
                    f.flush()
                    rows.append(row)
                    status = "ERROR" if row["error"] else ("ok" if row["success"] else "FAIL")
                    print(f"[{count}/{total}] {task_id} {strategy:<13} -> "
                          f"{row['final_tier'] or '-':<7} {status:<5} "
                          f"{row['latency_ms'] / 1000:.1f}s", flush=True)
        except KeyboardInterrupt:
            print("\nStopped early. Partial results are saved.")

    summary = summarize(rows)
    print("\n" + summary)
    (out_dir / (csv_path.stem + "_summary.txt")).write_text(summary, encoding="utf-8")
    print(f"\nSaved: {csv_path.name} and {csv_path.stem}_summary.txt in data/eval/")


if __name__ == "__main__":
    main()