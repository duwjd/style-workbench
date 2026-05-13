import { client } from "./client";
import type {
  PromptResponse,
  PromptListResponse,
  PromptCreateBody,
  PromptMetaUpdateBody,
  PromptVersionCreateBody,
  PromptVersionResponse,
  PromptVersionListResponse,
  PromptVersionCreateResponse,
  PromptUsageResponse,
  PromptFilters,
  PromptAbRequest,
  PromptAbResponse,
  PromptOptimizeRequest,
  PromptOptimizeResponse,
  PromptOptimizationListResponse,
} from "@/types/prompts";
import { PreconditionFailedError } from "@/types/prompts";
import type { AxiosResponse } from "axios";

/** GET /api/prompts レスポンスと ETag を同時に返す */
export interface PromptWithEtag {
  data: PromptResponse;
  etag: string;
}

function extractEtag(response: AxiosResponse): string {
  return response.headers["etag"] ?? "";
}

function buildFiltersParams(filters: PromptFilters): Record<string, string | number | undefined> {
  const params: Record<string, string | number | undefined> = {
    limit: filters.limit ?? 20,
    offset: filters.offset ?? 0,
  };
  if (filters.q) params["q"] = filters.q;
  if (filters.nodeType) {
    params["node_type"] = Array.isArray(filters.nodeType)
      ? filters.nodeType.join(",")
      : filters.nodeType;
  }
  if (filters.status) {
    params["status"] = Array.isArray(filters.status)
      ? filters.status.join(",")
      : filters.status;
  }
  if (filters.tags && filters.tags.length > 0) {
    params["tags"] = filters.tags.join(",");
  }
  return params;
}

function guard412(e: unknown): never {
  if (
    typeof e === "object" &&
    e !== null &&
    "response" in e &&
    (e as { response?: { status?: number } }).response?.status === 412
  ) {
    throw new PreconditionFailedError();
  }
  throw e;
}

export const promptsApi = {
  /** GET /api/prompts — 목록 조회 (필터 지원) */
  list: async (filters: PromptFilters = {}): Promise<PromptListResponse> => {
    const params = buildFiltersParams(filters);
    const response = await client.get<PromptListResponse>("/api/prompts", { params });
    return response.data;
  },

  /** GET /api/prompts/{id} — 단건 조회 (ETag 포함 반환) */
  getById: async (id: string): Promise<PromptWithEtag> => {
    const response = await client.get<PromptResponse>(`/api/prompts/${id}`);
    return {
      data: response.data,
      etag: extractEtag(response),
    };
  },

  /** POST /api/prompts — 신규 생성 */
  create: async (body: PromptCreateBody): Promise<PromptWithEtag> => {
    const response = await client.post<PromptResponse>("/api/prompts", body);
    return {
      data: response.data,
      etag: extractEtag(response),
    };
  },

  /** PUT /api/prompts/{id} — 메타 변경 (If-Match 필수) */
  updateMeta: async (
    id: string,
    body: PromptMetaUpdateBody,
    etag: string
  ): Promise<PromptWithEtag> => {
    try {
      const response = await client.put<PromptResponse>(`/api/prompts/${id}`, body, {
        headers: { "If-Match": etag },
      });
      return {
        data: response.data,
        etag: extractEtag(response),
      };
    } catch (e) {
      guard412(e);
    }
  },

  /** POST /api/prompts/{id}/versions — 새 버전 생성 (If-Match 필수) */
  createVersion: async (
    id: string,
    body: PromptVersionCreateBody,
    etag: string
  ): Promise<PromptVersionCreateResponse> => {
    try {
      const response = await client.post<PromptVersionCreateResponse>(
        `/api/prompts/${id}/versions`,
        body,
        { headers: { "If-Match": etag } }
      );
      return response.data;
    } catch (e) {
      guard412(e);
    }
  },

  /** GET /api/prompts/{id}/versions/{v} — 특정 버전 조회 */
  getVersion: async (id: string, version: number): Promise<PromptVersionResponse> => {
    const response = await client.get<PromptVersionResponse>(
      `/api/prompts/${id}/versions/${version}`
    );
    return response.data;
  },

  /** POST /api/prompts/{id}/versions/{v}/promote — current_version_id 변경 */
  promoteVersion: async (id: string, version: number): Promise<PromptResponse> => {
    const response = await client.post<PromptResponse>(
      `/api/prompts/${id}/versions/${version}/promote`
    );
    return response.data;
  },

  /** GET /api/prompts/{id}/usages?limit=&offset= — 사용처 paginate */
  listUsages: async (
    id: string,
    limit = 20,
    offset = 0
  ): Promise<{ items: PromptUsageResponse[]; total: number }> => {
    const response = await client.get<{ items: PromptUsageResponse[]; total: number }>(
      `/api/prompts/${id}/usages`,
      { params: { limit, offset } }
    );
    return response.data;
  },

  /** GET /api/prompts/{id}/versions/{v} (by ULID or integer) — 특정 버전 본문 조회 */
  getVersionById: async (id: string, versionId: string): Promise<PromptVersionResponse> => {
    const response = await client.get<PromptVersionResponse>(
      `/api/prompts/${id}/versions/${versionId}`
    );
    return response.data;
  },

  /** POST /api/prompts/{id}/ab — A/B 비교 실행 트리거 */
  triggerAb: async (
    id: string,
    body: PromptAbRequest
  ): Promise<PromptAbResponse> => {
    const response = await client.post<PromptAbResponse>(
      `/api/prompts/${id}/ab`,
      body
    );
    return response.data;
  },

  /** POST /api/prompts/{id}/versions/{v}/promote — current_version_id 변경 (by ULID) */
  promoteVersionById: async (id: string, versionId: string): Promise<PromptResponse> => {
    const response = await client.post<PromptResponse>(
      `/api/prompts/${id}/versions/${versionId}/promote`
    );
    return response.data;
  },

  /** GET /api/prompts/{id}/versions — 버전 목록 (version DESC 정렬, limit 기본 50) */
  listVersions: async (
    id: string,
    params?: { limit?: number; offset?: number }
  ): Promise<PromptVersionListResponse> => {
    const response = await client.get<PromptVersionListResponse>(
      `/api/prompts/${id}/versions`,
      { params: { limit: params?.limit ?? 50, offset: params?.offset ?? 0 } }
    );
    return response.data;
  },

  /** POST /api/prompts/{id}/optimize — F02 수동 트리거 */
  optimizePrompt: async (
    id: string,
    body: PromptOptimizeRequest
  ): Promise<PromptOptimizeResponse> => {
    const response = await client.post<PromptOptimizeResponse>(
      `/api/prompts/${id}/optimize`,
      body
    );
    return response.data;
  },

  /** GET /api/prompts/{id}/optimizations — F02 호출 이력 */
  listOptimizations: async (
    id: string,
    params?: { limit?: number; offset?: number }
  ): Promise<PromptOptimizationListResponse> => {
    const response = await client.get<PromptOptimizationListResponse>(
      `/api/prompts/${id}/optimizations`,
      { params: { limit: params?.limit ?? 20, offset: params?.offset ?? 0 } }
    );
    return response.data;
  },
};
