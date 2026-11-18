# RouteWise Frontend

An interactive, n8n-style workflow canvas for **RouteWise** — an intelligent tool that analyzes user queries, scores difficulty across 5 dimensions, and dynamically routes each query to the most cost-effective model tier.

Built with **React**, **TypeScript**, **Vite**, **Tailwind CSS**, and **@xyflow/react** (React Flow).

---

## Workflow Concept

```
[Query Input] ➔ [Difficulty Analyzer] ➔ [Router] ➔ [Small | Medium | Large Model] ➔ [Response & Validation]
```

* **Query Input**: Captures raw user task text and token metrics.
* **Difficulty Analyzer**: Scores Complexity, Reasoning, Context, Constraints, and Reliability (0–100 scale).
* **Cost & Tier Router**: Dynamically matches difficulty to model tier (Small, Medium, or Large).
* **Tiered Models**:
  * 🟢 **Small Tier**: `qwen2.5:0.5b` in the current local configuration.
  * 🟡 **Medium Tier**: `qwen2.5:1.5b` in the current local configuration.
  * 🟣 **Large/Strong Tier**: `qwen2.5:3b` in the current local configuration. “Large” is the router's relative tier name, not a 72B model.
* **Response & Validation**: Validates output syntax, schema, and returns response telemetry.

The displayed cost is an estimate based on configurable example prices; local Ollama inference does not incur that per-token provider charge. The configured model names are in the project-root `.env` file.

---

## Getting Started

### 1. Install Dependencies
From the `frontend/` directory:
```bash
npm install
```

### 2. Run the Development Server
```bash
npm run dev
```
The app will launch at `http://localhost:5173`.

### 3. Build for Production
```bash
npm run build
```

---

## Connecting to the Real Backend API

The project isolates all network communication inside [`src/api.ts`](./src/api.ts).

To connect to your running RouteWise FastAPI backend (by default on `http://127.0.0.1:8000`), update `routeQuery` in [`src/api.ts`](./src/api.ts):

The client waits for the backend response without a short browser-side timeout, since local Ollama models can take several seconds or longer to respond. It uses the simulated response only if the backend cannot be reached; backend HTTP errors are shown rather than replaced with simulated output.

```typescript
export async function routeQuery(query: string): Promise<RouteResult> {
  const response = await fetch('http://127.0.0.1:8000/api/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task: query,
      strategy: 'dynamic',
      enable_validation: true,
      enable_escalation: true,
      max_escalations: 2,
    }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  const data = await response.json();
  const res = data.result;
  const analysis = res.analysis;

  return {
    difficulty: Math.round((analysis.total_score / 10) * 100),
    tier: res.final_tier === 'strong' ? 'large' : res.final_tier,
    model: res.attempts[res.attempts.length - 1].model,
    reason: res.decision.reason,
    latencyMs: res.total_latency_ms,
    cost: res.total_estimated_cost,
    tokenCount: {
      input: analysis.estimated_input_tokens,
      output: Math.round(res.final_response.length / 4),
    },
    responseText: res.final_response,
    scores: {
      complexity: analysis.complexity_score,
      reasoning: analysis.reasoning_score,
      context: analysis.context_score,
      constraints: analysis.constraints_score,
      reliability: analysis.reliability_score,
    },
  };
}
```

---

## Features & UX Highlights

* **n8n-Inspired Nodes**: Rounded cards with status dots (`idle`, `running`, `done`), left/right connection handles, and color-coded tier badges.
* **Flowing Edge Animations**: Selected routing paths animate with a flowing stroke dash, while unchosen models fade to 40% opacity.
* **Side Inspector Panel**: Displays a 0–100 gauge, 5-factor score matrix, latency, token throughput, and estimated dollar costs.
* **Interactive Bottom History**: Replay previous queries and inspect past routes with one click.
* **Dark / Light Theme**: Polished developer tool aesthetic respecting `prefers-reduced-motion`.
