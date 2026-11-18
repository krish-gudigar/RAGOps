"""Inspect task-type regexes and expert-gate similarities for one prompt."""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.analyzer.task_types import detect_task_type_details
from app.config import Settings
from app.routing.expert_gate import ExpertGate, MockEmbedder, OllamaEmbedder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Prompt to inspect")
    parser.add_argument(
        "--mock", action="store_true",
        help="Use deterministic offline embeddings instead of the configured Ollama service",
    )
    args = parser.parse_args()

    settings = Settings()
    details = detect_task_type_details(args.prompt)
    print(f"task_type: {details.task_type}")
    print(f"matched_specific: {details.matched_specific}")
    print("regex signals:", "; ".join(details.signals) if details.signals else "none")

    if args.mock or os.getenv("PROVIDER_MODE", "mock").lower() != "ollama":
        embedder = MockEmbedder()
        cache_path = Path(__file__).resolve().parents[1] / "data" / "expert_embeddings.mock.json"
    else:
        embedder = OllamaEmbedder(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        cache_path = Path(__file__).resolve().parents[1] / "data" / "expert_embeddings.json"

    decision = ExpertGate(settings, embedder, cache_path=cache_path).decide(args.prompt)
    print("\nexpert scores:")
    if decision.scores:
        for expert, score in sorted(decision.scores.items()):
            print(f"  {expert}: {score:.3f}")
    else:
        print("  unavailable (regex selected an expert without embedding)")

    if decision.top_matches:
        print("\ntop matching examples:")
        for text, expert, score in sorted(
            decision.top_matches, key=lambda match: match[2], reverse=True
        )[:settings.embedding_top_k]:
            print(f"  {expert.value} {score:.3f}: {text}")

    print("\nfinal decision:")
    print(f"  expert: {decision.expert.value}")
    print(f"  gate_stage: {decision.stage}")
    print(f"  reason: {decision.reason}")
    print(f"  embedding_latency_ms: {decision.embedding_latency_ms}")


if __name__ == "__main__":
    main()
