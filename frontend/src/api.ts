import { RouteResult, Tier } from './types';

const BACKEND_URL = 'http://127.0.0.1:8000';

interface BackendExecutionResponse {
  result: {
    analysis: {
      total_score: number;
      estimated_input_tokens: number;
      complexity_score: number;
      reasoning_score: number;
      context_score: number;
      constraints_score: number;
      reliability_score: number;
    };
    decision?: {
      reason?: string;
      selected_model?: string;
      expert?: RouteResult['expert'];
      model_name?: string | null;
      gate_stage?: string | null;
      gate_reason?: string | null;
      fallback_reason?: string | null;
      embedding_latency_ms?: number;
      expert_scores?: Record<string, number>;
    } | null;
    attempts: Array<{
      model?: string;
      model_name?: string | null;
      response?: string;
    }>;
    final_tier: string;
    final_response: string;
    total_latency_ms: number;
    total_estimated_cost: number;
    expert?: RouteResult['expert'];
    model_name?: string | null;
    gate_stage?: string | null;
    gate_reason?: string | null;
    embedding_latency_ms?: number;
  };
}

export async function routeQuery(query: string, useExperts: boolean): Promise<RouteResult> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task: query,
        strategy: 'dynamic',
        use_experts: useExperts,
        enable_validation: true,
        enable_escalation: true,
        max_escalations: 2,
      }),
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Could not connect to the backend at ${BACKEND_URL}. Start the FastAPI server and try again.`
      );
    }
    throw error;
  }

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Backend returned HTTP ${response.status}: ${errorBody.slice(0, 200)}`);
  }

  const data = (await response.json()) as BackendExecutionResponse;
  const result = data.result;
  const analysis = result.analysis;
  const decision = result.decision;
  const lastAttempt = result.attempts?.[result.attempts.length - 1];
  const tierMap: Record<string, Tier> = {
    small: 'small',
    medium: 'medium',
    strong: 'large',
  };

  return {
    difficulty: Math.round((analysis.total_score / 10) * 100),
    tier: tierMap[result.final_tier] || 'medium',
    model: lastAttempt?.model_name || lastAttempt?.model || decision?.model_name || decision?.selected_model || 'Unknown',
    reason: decision?.reason || 'Dynamic route selected by backend.',
    expert: result.expert || decision?.expert || 'general',
    gateStage: result.gate_stage || decision?.gate_stage || null,
    gateReason: result.gate_reason || decision?.gate_reason || null,
    fallbackReason: decision?.fallback_reason || null,
    expertScores: decision?.expert_scores || {},
    embeddingLatencyMs: result.embedding_latency_ms || decision?.embedding_latency_ms || 0,
    latencyMs: result.total_latency_ms,
    cost: result.total_estimated_cost,
    tokenCount: {
      input: analysis.estimated_input_tokens,
      output: Math.round((result.final_response || '').length / 4),
    },
    responseText: result.final_response || lastAttempt?.response || 'No response returned.',
    scores: {
      complexity: analysis.complexity_score,
      reasoning: analysis.reasoning_score,
      context: analysis.context_score,
      constraints: analysis.constraints_score,
      reliability: analysis.reliability_score,
    },
    source: 'backend',
  };
}
