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

export interface DagNode {
  id: string;
  type: "text_generation" | "image_generation" | "video_generation" | "composition";
  model: { provider: string; modelId: string };
  promptTemplate: string;
  inputs: NodeInput[];
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
  status: "pending" | "succeeded" | "failed";
  totalCost: number | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  nodeExecutions: NodeExecution[];
}
