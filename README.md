# RouteWise

RouteWise is an educational, explainable LLM router with a FastAPI backend and
a Streamlit UI. It analyzes task difficulty and routes to a small, medium, or
strong model tier. Optional expert-pool routing independently chooses a
general, coding, or reasoning expert.

The default provider is a local Ollama instance when `PROVIDER_MODE=ollama` is
set in `.env`; otherwise the offline mock provider is used.

## Run locally

Start the Ollama desktop app (or run `ollama serve`) if using local models.
Then open separate terminals from the project root:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

```powershell
streamlit run frontend/streamlit_app.py
```

The Streamlit app opens in a browser. The FastAPI docs are at
`http://127.0.0.1:8000/docs`. Python packages used by the backend, including
NumPy for embeddings, must be available in the active Python environment.

## Expert-pool routing

Expert routing is opt-in (`use_experts: false` by default), so leaving it off
preserves the existing tier-only routing behavior. When enabled, RouteWise
makes two independent decisions:

1. **Expert:** The ordered task-type regexes short-circuit to coding or
   reasoning when a specific type matches. General-question and unknown
   detections are treated as non-specific. Otherwise, the embedding gate
   compares the prompt with the editable example bank.
2. **Tier:** The existing difficulty score chooses small, medium, or strong.
   The existing reliability safety rule is unchanged.

Every expert-enabled decision includes the gate stage and a human-readable
reason. If the best embedding score is below the minimum, the top two experts
are too close, or embedding is unavailable, the gate chooses the general
expert. If a configured expert has no model for the selected tier, RouteWise
uses the general model for that tier and records a `fallback_reason`.

### Settings

Defaults are in `backend/app/config.py` and are also exposed through
`GET /api/config` and the existing settings API. For example, enable the gate
and configure its thresholds with:

```json
{
  "use_experts": true,
  "embedding_model": "all-minilm",
  "embedding_top_k": 3,
  "embedding_min_score": 0.45,
  "embedding_min_margin": 0.05,
  "embedding_timeout_s": 15
}
```

Send this JSON to `POST /api/settings` to persist it in
`data/settings.json`. The `/api/execute` endpoint also accepts an optional
per-request `use_experts` boolean, which overrides the global setting for that
run. `/api/compare` includes an `expert_pool` strategy.

| Expert | small | medium | strong | Default |
|---|---|---|---|---|
| general | Current `SMALL_MODEL` | Current `MEDIUM_MODEL` | Current `STRONG_MODEL` | Configured through `.env`; unchanged |
| coding | `qwen2.5-coder:0.5b` | `qwen2.5-coder:1.5b` | `qwen2.5-coder:3b` | Example tags; verify availability before use |
| reasoning | Not configured | Not configured | Not configured | Empty; uses the general model until configured |

Coding model names can be overridden with `CODING_SMALL_MODEL`,
`CODING_MEDIUM_MODEL`, and `CODING_STRONG_MODEL` in `.env`. The model table and
expert model price entries are also persisted by the settings API. New expert
model prices initially copy the corresponding general tier's configurable
prices. Local inference does not incur those example token charges.

Before using Ollama embeddings or expert models, pull the desired tags and
check what is installed:

```powershell
ollama pull all-minilm
ollama list
```

The coding model tags in the table are examples and may need to be changed to
tags available from Ollama. A reasoning model can be assigned through
`expert_models` in `POST /api/settings`, for example:

```json
{
  "expert_models": {
    "reasoning": {
      "medium": "your-installed-reasoning-model"
    }
  }
}
```

Expect slower first responses while Ollama loads embedding and generation
models, especially when several different models are used.

### Editing examples and tuning the gate

Edit [`data/expert_examples.yaml`](./data/expert_examples.yaml) to tune the
prompt examples. Keep the existing simple YAML shape: expert headings
(`coding:`, `reasoning:`, `general:`) and double-quoted prompt strings on
indented `-` lines. Each expert currently has 18 examples. The embedding cache
is written to `data/expert_embeddings.json`; vectors are reused by embedding
model name and example-text hash, so changing the model or an example causes
that vector to be recomputed.

Inspect regex matches, scores, nearest examples, and the final decision with:

```powershell
python scripts/inspect_gate.py --mock "my app keeps dying after login"
python scripts/inspect_gate.py "why does this total come out wrong"
```

The first command is deterministic and offline. The second uses Ollama for
embeddings when `PROVIDER_MODE=ollama`; omit `--mock` to use the configured
provider mode. The threshold defaults are placeholders, not calibrated values;
use representative prompts and this inspection tool to tune them.

Example timeline for a regex-matched coding task:

```text
Task received
Task analyzed: coding, score 4/10 (medium difficulty)
Dynamic routing: medium model selected
Expert gate: coding via regex (coding detected by regex -> coding expert.); embedding overhead 0ms
Response generated by the coding expert's medium model (qwen2.5-coder:1.5b)
Validation passed
Final response returned
```

## Tests

Run the backend tests offline from the project root:

```powershell
python -m pytest -q
```