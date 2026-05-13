export interface StyleListItem {
  id: string;
  name: string;
  concept: string;
  vertical: string;
  tags: string[];
  status: "draft" | "approved" | "rejected";
  currentVersion: number;
  versionId: string;
  createdAt: string;
}

export interface NodeInput {
  source: string;
  role: string;
}

export interface VariableMapping {
  source: "user_input" | "node_output" | "constant";
  role?: string;
  nodeId?: string;
  value?: string;
}

export interface DagNode {
  id: string;
  type: "text_generation" | "image_generation" | "video_generation" | "composition";
  model: { provider: string; modelId: string };
  promptTemplate: string;
  inputs: NodeInput[];
  variableMapping?: Record<string, VariableMapping>;
}

export interface DagEdge {
  source: string;
  target: string;
}

export interface Dag {
  nodes: DagNode[];
  edges: DagEdge[];
  variables: string[];
}

export interface StyleDetail extends StyleListItem {
  dag: Dag;
}

export interface StyleSummary {
  id: string;
  name: string;
  versionId: string;
  tags: string[];
  createdAt: string;
}

export interface NodeExecution {
  id: string;
  nodeId: string;
  nodeType: string;
  modelProvider: string | null;
  modelId: string | null;
  artifactUrl: string | null;
  cost: number | null;
  status: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface Run {
  id: string;
  styleVersionId: string;
  styleId: string;
  status: "pending" | "succeeded" | "failed" | "aborted";
  totalCost: number | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  nodeExecutions: NodeExecution[];
}

// ─── F01: Retry Attempts ─────────────────────────────────────────────────────

export interface RetryAttempt {
  id: string;
  nodeId: string;
  attemptNumber: number;
  promptVersionIdUsed: string | null;
  retryGuidance: Record<string, unknown> | null;
  evaluationId: string | null;
  costWon: string; // Decimal → string 직렬화
  passed: boolean | null; // null = 예산 초과로 evaluator 미호출
  failedDimensions: string[];
  startedAt: string; // ISO 8601
  finishedAt: string | null;
}

export interface RetryAttemptList {
  runId: string;
  attempts: RetryAttempt[];
  totalAttempts: number;
  succeeded: boolean | null;
}

// ─── POST /api/styles/:id/versions — request body ────────────────────────────

/** POST /api/styles/:id/versions — request body */
export interface SaveDagPayload {
  dag: {
    nodes: Array<{
      id: string;
      type: string;
      model: { provider: string; modelId: string };
      promptTemplate: string;
      inputs: NodeInput[];
    }>;
    edges: Array<{ source: string; target: string }>;
    variables: string[];
  };
  brief?: string;
}

/** POST /api/styles/:id/versions — response */
export interface SaveDagResponse {
  versionId: string;
  version: number;
  currentVersion: number;
  createdAt: string;
}
