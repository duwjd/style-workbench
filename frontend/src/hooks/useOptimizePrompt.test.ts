/**
 * F02 — useOptimizePrompt 단위 테스트
 *
 * 검증 항목:
 *   - mutation 성공 (succeeded=true) 시 onSuccess 콜백 호출
 *   - mutation 성공 (succeeded=false) 시도 onSuccess 콜백 호출 (로직 분기는 caller)
 *   - mutation 실패 (HTTP 4xx) 시 onError 콜백 호출
 *   - succeeded=true 시 promptVersions 캐시 무효화
 *   - succeeded=false 시 promptVersions 캐시 무효화 안됨
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useOptimizePrompt } from "./useOptimizePrompt";
import type { PromptOptimizeResponse } from "@/types/prompts";

// ─── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/api/prompts", () => ({
  promptsApi: {
    optimizePrompt: vi.fn(),
    listOptimizations: vi.fn().mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    }),
  },
}));

import { promptsApi } from "@/api/prompts";

const mockOptimizePrompt = vi.mocked(promptsApi.optimizePrompt);

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: qc }, children);
  };
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

const SUCCESS_RESPONSE: PromptOptimizeResponse = {
  optimizationId: "po-001",
  promptId: "prm-001",
  parentVersionId: "pmv-001",
  newVersionId: "pmv-002",
  changeSummary: "lighting 개선",
  costWon: "312.50",
  latencyMs: 4523,
  succeeded: true,
  failureReason: null,
};

const FAILURE_RESPONSE: PromptOptimizeResponse = {
  optimizationId: "po-002",
  promptId: "prm-001",
  parentVersionId: "pmv-001",
  newVersionId: null,
  changeSummary: null,
  costWon: "100.00",
  latencyMs: 2000,
  succeeded: false,
  failureReason: "placeholder {role} 누락",
};

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("useOptimizePrompt", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("mutation 성공(succeeded=true) 시 onSuccess 콜백이 result와 함께 호출된다", async () => {
    mockOptimizePrompt.mockResolvedValue(SUCCESS_RESPONSE);
    const onSuccess = vi.fn();
    const qc = makeQueryClient();

    const { result } = renderHook(
      () => useOptimizePrompt({ promptId: "prm-001", onSuccess }),
      { wrapper: makeWrapper(qc) }
    );

    act(() => {
      result.current.mutate({
        retryGuidance: { instruction: "fix" },
        failedDimensions: ["lighting"],
        parentVersionId: "pmv-001",
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(onSuccess).toHaveBeenCalledWith(SUCCESS_RESPONSE);
  });

  it("mutation 성공(succeeded=false) 시 onSuccess 콜백이 호출된다 (caller가 분기 처리)", async () => {
    mockOptimizePrompt.mockResolvedValue(FAILURE_RESPONSE);
    const onSuccess = vi.fn();
    const qc = makeQueryClient();

    const { result } = renderHook(
      () => useOptimizePrompt({ promptId: "prm-001", onSuccess }),
      { wrapper: makeWrapper(qc) }
    );

    act(() => {
      result.current.mutate({
        retryGuidance: { instruction: "fix" },
        failedDimensions: ["mood"],
        parentVersionId: "pmv-001",
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(onSuccess).toHaveBeenCalledWith(FAILURE_RESPONSE);
  });

  it("HTTP 4xx 에러 시 onError 콜백이 호출된다", async () => {
    const networkError = new Error("404 Not Found");
    mockOptimizePrompt.mockRejectedValue(networkError);
    const onError = vi.fn();
    const qc = makeQueryClient();

    const { result } = renderHook(
      () => useOptimizePrompt({ promptId: "prm-001", onError }),
      { wrapper: makeWrapper(qc) }
    );

    act(() => {
      result.current.mutate({
        retryGuidance: { instruction: "fix" },
        failedDimensions: ["composition"],
        parentVersionId: "pmv-001",
      });
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(onError).toHaveBeenCalledWith(networkError);
  });

  it("succeeded=true 시 promptOptimizations 캐시가 무효화된다", async () => {
    mockOptimizePrompt.mockResolvedValue(SUCCESS_RESPONSE);
    const qc = makeQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    const { result } = renderHook(
      () => useOptimizePrompt({ promptId: "prm-001" }),
      { wrapper: makeWrapper(qc) }
    );

    act(() => {
      result.current.mutate({
        retryGuidance: { instruction: "fix" },
        failedDimensions: ["lighting"],
        parentVersionId: "pmv-001",
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // optimizations 캐시 무효화 확인
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["promptOptimizations", "prm-001"],
      })
    );

    // versions 캐시도 무효화 (succeeded=true)
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["promptVersions", "prm-001"],
      })
    );
  });

  it("succeeded=false 시 promptVersions 캐시는 무효화되지 않는다", async () => {
    mockOptimizePrompt.mockResolvedValue(FAILURE_RESPONSE);
    const qc = makeQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    const { result } = renderHook(
      () => useOptimizePrompt({ promptId: "prm-001" }),
      { wrapper: makeWrapper(qc) }
    );

    act(() => {
      result.current.mutate({
        retryGuidance: { instruction: "fix" },
        failedDimensions: ["mood"],
        parentVersionId: "pmv-001",
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // optimizations 캐시는 무효화됨
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["promptOptimizations", "prm-001"],
      })
    );

    // versions 캐시는 무효화 안됨 (succeeded=false, newVersionId=null)
    expect(invalidateSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["promptVersions", "prm-001"],
      })
    );
  });
});
