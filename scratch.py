import sys
from pathlib import Path

# Add backend directory to path so 'app' can be imported
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.analyzer.task_analyzer import TaskAnalyzer

a = TaskAnalyzer()
tasks = [
    "Fix the bug in my login function, it throws a KeyError.",
    "Write a haiku about monsoon rain.",
    "Design a scalable architecture for a chat app with 1M users.",
]
for t in tasks:
    r = a.analyze(t)
    print(r.total_score, r.difficulty, r.task_type, "|", t)
    print("   ", r.detected_signals)