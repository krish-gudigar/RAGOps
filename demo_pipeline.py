from app.execution.metrics import compute_metrics
from app.execution.orchestrator import Orchestrator
from app.execution.timeline import build_timeline
from app.models.requests import TaskRequest
from app.providers.mock_provider import MockModelProvider
from app.storage.answer_cache import AnswerCache, CachingProvider
from app.storage.repository import HistoryRepository

repo = HistoryRepository("data/demo_history.jsonl")
repo.clear()  # start fresh each time you run the demo
cache = AnswerCache("data/demo_cache.jsonl")
orch = Orchestrator(provider=CachingProvider(MockModelProvider(), cache), repository=repo)

tasks = [
    ("Translate 'Good morning' to French.", "dynamic"),
    ("Fix the bug in my login function, it throws a KeyError.", "dynamic"),
    ("Design a scalable architecture for a chat app with 1M users.", "always_small"),
    ("Explain how DNS works [mock:needs=strong]", "dynamic"),
]

for task, strategy in tasks:
    result = orch.execute(TaskRequest(task=task, strategy=strategy))
    print("\n==", task, f"({strategy})")
    print("   why:", result.decision.reason)
    for step in build_timeline(result):
        print("   -", step)
    print(f"   success={result.success} cost=${result.total_estimated_cost:.6f} "
          f"latency={result.total_latency_ms}ms")

print("\nMETRICS:", compute_metrics(repo.all_results()).model_dump())
print("cache entries:", len(cache), "| history lines:", len(repo.all_records()))