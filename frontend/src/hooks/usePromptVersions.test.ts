/**
 * F05 단계 5 — usePromptVersions 단위 테스트
 *
 * listVersions API 호출 여부 및 enabled 조건 검증.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { usePromptVersions } from "./usePromptVersions";
import * as promptsApiModule from "@/api/prompts";
import type { PromptVersionListResponse } from "@/types/prompts";

vi.mock("@/api/prompts", () => ({
  promptsApi: {
    listVersions: vi.fn(),
  },
}));

const VERSION_1 = {
  id: "pmv-001",
  version: 1,
  body: "Hello {name}",
  declaredVariables: [{ name: "name", role: "person_name", required: true }],
  modelDefault: null,
  parentVersionId: null,
  changeNote: null,
  createdAt: "2026-05-01T00:00:00Z",
  createdBy: null,
};

const VERSION_2 = {
  id: "pmv-002",
  version: 2,
  body: "Hi there {name}",
  declaredVariables: [{ name: "name", role: "person_name", required: true }],
  modelDefault: null,
  parentVersionId: "pmv-001",
  changeNote: "tone 변경",
  createdAt: "2026-05-02T00:00:00Z",
  createdBy: null,
};

const MOCK_LIST_2: PromptVersionListResponse = {
  items: [VERSION_2, VERSION_1],
  total: 2,
  limit: 50,
  offset: 0,
};

const MOCK_LIST_1: PromptVersionListResponse = {
  items: [VERSION_1],
  total: 1,
  limit: 50,
  offset: 0,
};

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("usePromptVersions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("promptId가 null이면 API를 호출하지 않는다", () => {
    renderHook(() => usePromptVersions(null), { wrapper: makeWrapper() });
    expect(promptsApiModule.promptsApi.listVersions).not.toHaveBeenCalled();
  });

  it("promptId가 undefined이면 API를 호출하지 않는다", () => {
    renderHook(() => usePromptVersions(undefined), { wrapper: makeWrapper() });
    expect(promptsApiModule.promptsApi.listVersions).not.toHaveBeenCalled();
  });

  it("promptId가 있으면 listVersions를 호출하고 items를 반환한다", async () => {
    vi.mocked(promptsApiModule.promptsApi.listVersions).mockResolvedValue(MOCK_LIST_2);

    const { result } = renderHook(() => usePromptVersions("prm-001"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(promptsApiModule.promptsApi.listVersions).toHaveBeenCalledWith("prm-001", undefined);
    expect(result.current.data?.items).toHaveLength(2);
    expect(result.current.data?.total).toBe(2);
  });

  it("versions >= 2이면 items 길이가 2 이상이다 (A/B 버튼 활성화 조건)", async () => {
    vi.mocked(promptsApiModule.promptsApi.listVersions).mockResolvedValue(MOCK_LIST_2);

    const { result } = renderHook(() => usePromptVersions("prm-001"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect((result.current.data?.items ?? []).length).toBeGreaterThanOrEqual(2);
  });

  it("versions === 1이면 items 길이가 1이다 (A/B 버튼 disabled 조건)", async () => {
    vi.mocked(promptsApiModule.promptsApi.listVersions).mockResolvedValue(MOCK_LIST_1);

    const { result } = renderHook(() => usePromptVersions("prm-001"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect((result.current.data?.items ?? []).length).toBe(1);
  });

  it("params를 전달하면 listVersions에 그대로 전달된다", async () => {
    vi.mocked(promptsApiModule.promptsApi.listVersions).mockResolvedValue(MOCK_LIST_2);

    const params = { limit: 10, offset: 20 };
    renderHook(() => usePromptVersions("prm-001", params), { wrapper: makeWrapper() });

    await waitFor(() =>
      expect(promptsApiModule.promptsApi.listVersions).toHaveBeenCalledWith("prm-001", params)
    );
  });

  it("API 실패 시 isError가 true가 된다", async () => {
    vi.mocked(promptsApiModule.promptsApi.listVersions).mockRejectedValue(
      new Error("Network error")
    );

    const { result } = renderHook(() => usePromptVersions("prm-001"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});
