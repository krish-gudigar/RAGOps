import { RouteResult, Tier } from './types';

const BACKEND_URL = 'http://127.0.0.1:8000';

/**
 * Intelligent client-side fallback if backend server is not running
 */
function mockRouteQuery(query: string): RouteResult {
  const lower = query.toLowerCase();

  const isCoding = /\b(code|function|debug|python|rust|algorithm|script|api|sql|refactor|ast|class)\b/.test(lower);
  const isHardMath = /\b(derivative|integral|proof|prove|theorem|solve|matrix|probability)\b/.test(lower);
  const isArchitecture = /\b(architecture|microservices|distributed|concurrency|race condition|scalab|consensus|raft)\b/.test(lower);
  const isStepByStep = /\b(step[- ]by[- ]step|trade-?offs?|deep dive|explain why|compare)\b/.test(lower);
  const isSimple = /\b(translate|hello|hi|what is|capital of|joke|sum|summarize in one sentence)\b/.test(lower);

  let difficultyScore = 20;
  let tier: Tier = 'small';
  let model = 'Client-side simulation (small tier)';
  let reason = 'Simple prompt with minimal reasoning requirements routed to small tier.';
  let cost = 0.00008;
  let latencyMs = 280;
  let responseText = '';

  const scores = {
    complexity: 0,
    reasoning: 0,
    context: Math.min(2, Math.floor(query.length / 200)),
    constraints: /\b(only|json|max|under|must|format)\b/.test(lower) ? 1 : 0,
    reliability: 1,
  };

  if (isArchitecture || (isCoding && isStepByStep) || (isHardMath && query.length > 50)) {
    scores.complexity = 2;
    scores.reasoning = 2;
    scores.reliability = 2;
    difficultyScore = 88;
    tier = 'large';
    model = 'Client-side simulation (large tier)';
    reason = 'High complexity architecture/multi-step reasoning detected. Requires deep synthesis and high reliability.';
    cost = 0.0038;
    latencyMs = 1450;
    responseText = `[Large Tier Execution - ${model}]\n\nAnalysis & Plan:\n1. Deconstructed requirement into invariant architectural contracts.\n2. Addressed concurrency boundaries and failure recovery models.\n3. Verified edge cases against formal consistency semantics.\n\nOptimal Implementation:\nSuccessfully generated comprehensive, fault-tolerant solution.`;
  } else if (isCoding || isHardMath || isStepByStep || query.length > 120) {
    scores.complexity = 1;
    scores.reasoning = 1;
    scores.reliability = 1;
    difficultyScore = 54;
    tier = 'medium';
    model = 'Client-side simulation (medium tier)';
    reason = 'Moderate complexity code generation or structured logic. Medium tier balances speed and accuracy.';
    cost = 0.00045;
    latencyMs = 580;
    responseText = `[Medium Tier Execution - ${model}]\n\nHere is the solution tailored to your request:\n\`\`\`python\ndef solution(data):\n    # Optimized implementation\n    return [item for item in data if validate(item)]\n\`\`\`\nValid syntax checked and basic edge conditions handled.`;
  } else if (isSimple || query.length < 50) {
    scores.complexity = 0;
    scores.reasoning = 0;
    scores.reliability = 0;
    difficultyScore = 18;
    tier = 'small';
    model = 'Client-side simulation (small tier)';
    reason = 'Low complexity inquiry or direct transform. Small tier fulfills request with lowest cost and sub-second latency.';
    cost = 0.00007;
    latencyMs = 210;
    responseText = `[Small Tier Execution - ${model}]\n\nDirect response:\nHere is the translated/direct response to your prompt. Resolved cleanly with low resource overhead.`;
  } else {
    scores.complexity = 1;
    scores.reasoning = 1;
    scores.reliability = 1;
    difficultyScore = 42;
    tier = 'medium';
    model = 'Client-side simulation (medium tier)';
    reason = 'Standard query with modest explanation requirements.';
    cost = 0.00035;
    latencyMs = 510;
    responseText = `[Medium Tier Execution - ${model}]\n\nResponse:\nCompleted your request directly with structured points.`;
  }

  return {
    difficulty: difficultyScore,
    tier,
    model,
    reason,
    latencyMs,
    cost,
    tokenCount: {
      input: Math.max(12, Math.floor(query.length / 4)),
      output: Math.floor(responseText.length / 4),
    },
    responseText,
    scores,
    source: 'mock',
  };
}

/**
 * Uses the real backend and falls back to simulation only when it cannot be reached.
 */
export async function routeQuery(query: string): Promise<RouteResult> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/execute`, {
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
  } catch (err) {
    if (!(err instanceof TypeError)) {
      throw err;
    }

    console.warn(
      `[RouteWise] Could not reach backend (${err}). Falling back to client-side simulation.`,
      `\nTo use real Ollama models:`,
      `\n  1. Start Ollama: open the Ollama app or run "ollama serve"`,
      `\n  2. Start backend: cd backend && ../.venv/Scripts/uvicorn.exe app.main:app --port 8000 --reload`,
      `\n  3. Start frontend: cd frontend && npm run dev`
    );

    // Fallback smoothly to client-side mock
    await new Promise((r) => setTimeout(r, 350));
    return { ...mockRouteQuery(query), source: 'mock' };
  }

  if (!response.ok) {
    const errBody = await response.text();
    console.error(`[RouteWise] Backend HTTP ${response.status}:`, errBody);
    throw new Error(`Backend returned HTTP ${response.status}: ${errBody.slice(0, 200)}`);
  }

  const data = await response.json();
  const res = data.result;
  const analysis = res.analysis;
  const lastAttempt = res.attempts?.[res.attempts.length - 1];

  const tierMap: Record<string, Tier> = {
    small: 'small',
    medium: 'medium',
    strong: 'large',
  };

  return {
    difficulty: Math.round(((analysis.total_score || 0) / 10) * 100),
    tier: tierMap[res.final_tier] || 'medium',
    model: lastAttempt?.model || res.decision?.selected_model || 'Unknown',
    reason: res.decision?.reason || 'Dynamic route selected by backend.',
    latencyMs: res.total_latency_ms || 320,
    cost: res.total_estimated_cost || 0.0001,
    tokenCount: {
      input: analysis.estimated_input_tokens || Math.max(10, Math.floor(query.length / 4)),
      output: Math.round((res.final_response || '').length / 4),
    },
    responseText: res.final_response || lastAttempt?.response || 'No response returned.',
    scores: {
      complexity: analysis.complexity_score || 0,
      reasoning: analysis.reasoning_score || 0,
      context: analysis.context_score || 0,
      constraints: analysis.constraints_score || 0,
      reliability: analysis.reliability_score || 0,
    },
    source: 'backend',
  };
}