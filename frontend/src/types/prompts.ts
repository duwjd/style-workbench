// ─── F05 Prompt Library types ────────────────────────────────────────────────

export type PromptNodeType = "text" | "image" | "video" | "composition";
export type PromptStatus = "draft" | "reviewing" | "approved" | "deprecated";

export interface DeclaredVariable {
  name: string;
  role: string;
  required: boolean;
}

export interface ModelDefault {
  provider: string;
  modelId: string;
}

export interface PromptVersionResponse {
  id: string;
  version: number;
  body: string;
  declaredVariables: DeclaredVariable[];
  modelDefault: ModelDefault | null;
  parentVersionId: string | null;
  changeNote: string | null;
  createdAt: string;
  createdBy: string | null;
}

export interface PromptUsageResponse {
  styleVersionId: string;
  styleName: string | null;
  nodeId: string;
  pinned: boolean;
  lastRunScore: number | null;
}

export interface PromptResponse {
  id: string;
  name: string;
  nodeType: PromptNodeType;
  status: PromptStatus;
  owner: string | null;
  tags: string[];
  currentVersion: PromptVersionResponse | null;
  usages: PromptUsageResponse[];
  usageCountTotal: number;
  createdAt: string;
  updatedAt: string;
}

export interface PromptListResponse {
  items: PromptResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface PromptVersionListResponse {
  items: PromptVersionResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface PromptVersionCreateResponse {
  version: PromptVersionResponse;
  warnings: string[];
}

// ─── Request types ────────────────────────────────────────────────────────────

export interface PromptCreateBody {
  name: string;
  nodeType: PromptNodeType;
  tags?: string[];
  body: string;
  declaredVariables?: DeclaredVariable[];
  modelDefault?: ModelDefault | null;
  changeNote?: string | null;
}

export interface PromptMetaUpdateBody {
  name?: string;
  tags?: string[];
  status?: PromptStatus;
}

export interface PromptVersionCreateBody {
  body: string;
  declaredVariables: DeclaredVariable[];
  changeNote?: string | null;
  modelDefault?: ModelDefault | null;
}

export interface PromptFilters {
  nodeType?: PromptNodeType | PromptNodeType[];
  status?: PromptStatus | PromptStatus[];
  tags?: string[];
  q?: string;
  limit?: number;
  offset?: number;
}

// ─── A/B comparison ───────────────────────────────────────────────────────────

export interface PromptAbRequest {
  fromVersion: string;
  toVersion: string;
  styleVersionId: string;
  userInput: Record<string, string>;
}

export interface PromptAbResponse {
  abId: string;
  promptId: string;
  fromVersionId: string;
  toVersionId: string;
  styleVersionId: string;
  fromRunId: string | null;
  toRunId: string | null;
  status: "running" | "done" | "failed";
}

// ─── F02 Prompt Optimizer types ───────────────────────────────────────────────

/**
 * POST /api/prompts/{id}/optimize 요청 본문.
 * Mode A: evaluation_id만 전달.
 * Mode B: retry_guidance + failed_dimensions + parent_version_id 직접 입력.
 */
export type PromptOptimizeRequest =
  | { evaluationId: string }
  | {
      retryGuidance: Record<string, unknown>;
      failedDimensions: string[];
      parentVersionId: string;
    };

/** POST /api/prompts/{id}/optimize 응답 */
export interface PromptOptimizeResponse {
  optimizationId: string;
  promptId: string;
  parentVersionId: string;
  newVersionId: string | null;
  changeSummary: string | null;
  costWon: string;
  latencyMs: number | null;
  succeeded: boolean;
  failureReason: string | null;
}

/** GET /api/prompts/{id}/optimizations 응답의 단건 항목 */
export interface PromptOptimizationSummary {
  optimizationId: string;
  parentVersionId: string;
  newVersionId: string | null;
  changeSummary: string | null;
  costWon: string;
  succeeded: boolean;
  failureReason: string | null;
  createdAt: string;
}

/** GET /api/prompts/{id}/optimizations 응답 */
export interface PromptOptimizationListResponse {
  items: PromptOptimizationSummary[];
  total: number;
  limit: number;
  offset: number;
}

// ─── ETag error ───────────────────────────────────────────────────────────────

export class PreconditionFailedError extends Error {
  readonly status = 412;
  constructor(message = "다른 사용자가 이 항목을 수정했습니다. 새로고침 후 다시 시도해주세요.") {
    super(message);
    this.name = "PreconditionFailedError";
  }
}
