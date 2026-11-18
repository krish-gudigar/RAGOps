export type Tier = 'small' | 'medium' | 'large';

export type NodeStatus = 'idle' | 'running' | 'done';

export type NodeType =
  | 'query_input'
  | 'analyzer'
  | 'router'
  | 'model_small'
  | 'model_medium'
  | 'model_large'
  | 'response';

export interface RouteResult {
  difficulty: number; // 0 - 100 scale
  tier: Tier;
  model: string;
  reason: string;
  latencyMs: number;
  cost: number;
  tokenCount: {
    input: number;
    output: number;
  };
  responseText: string;
  scores: {
    complexity: number;
    reasoning: number;
    context: number;
    constraints: number;
    reliability: number;
  };
  /** Where the response came from: real Ollama backend or client-side simulation */
  source: 'backend' | 'mock';
}

export interface QueryHistoryItem {
  id: string;
  query: string;
  timestamp: string;
  result: RouteResult;
}

export interface CustomNodeData extends Record<string, unknown> {
  nodeType: NodeType;
  title: string;
  subtitle: string;
  tier?: Tier;
  status: NodeStatus;
  isActivePath?: boolean;
  isDimmed?: boolean;
  result?: RouteResult | null;
  currentQuery?: string;
}
