import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { useRetryAttempts } from "./useRetryAttempts";
import * as runsApi from "@/api/runs";
import type { RetryAttemptList } from "@/types";

vi.mock("@/api/runs", () => ({
  runsApi: {
    getRetryAttempts: vi.fn(),
  },
  subscribeRun: vi.fn(() => () => {}),
}));

const MOCK_LIST: RetryAttemptList = {
  runId: "run-1",
  attempts: [
    {
      id: "rta-1",
      nodeId: "img1",
      attemptNumber: 0,
      promptVersionIdUsed: null,
      retryGuidance: null,
      evaluationId: "eval-1",
      costWon: "12500.00",
      passed: false,
      failedDimensions: ["composition"],
      startedAt: "2026-05-08T03:14:22Z",
      finishedAt: "2026-05-08T03:15:01Z",
    },
    {
      id: "rta-2",
      nodeId: "img1",
      attemptNumber: 1,
      promptVersionIdUsed: "pmv-001",
      retryGuidance: { instruction: "좌측 조명으로 변경" },
      evaluationId: "eval-2",
      costWon: "12500.00",
      passed: true,
      failedDimensions: [],
      startedAt: "2026-05-08T03:15:30Z",
      finishedAt: "2026-05-08T03:16:08Z",
    },
  ],
  totalAttempts: 2,
  succeeded: true,
};

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useRetryAttempts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("runId가 undefined이면 쿼리하지 않는다", () => {
    renderHook(() => useRetryAttempts(undefined), {
      wrapper: makeWrapper(),
    });
    expect(runsApi.runsApi.getRetryAttempts).not.toHaveBeenCalled();
  });

  it("runId가 있으면 getRetryAttempts를 호출한다", async () => {
    vi.mocked(runsApi.runsApi.getRetryAttempts).mockResolvedValue(MOCK_LIST);

    const { result } = renderHook(() => useRetryAttempts("run-1"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(runsApi.runsApi.getRetryAttempts).toHaveBeenCalledWith("run-1");
    expect(result.current.data).toEqual(MOCK_LIST);
  });

  it("초기 상태는 isLoading=true이다", () => {
    vi.mocked(runsApi.runsApi.getRetryAttempts).mockImplementation(
      () => new Promise(() => {}) // 영원히 pending
    );

    const { result } = renderHook(() => useRetryAttempts("run-1"), {
      wrapper: makeWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it("API 실패 시 isError=true이다", async () => {
    vi.mocked(runsApi.runsApi.getRetryAttempts).mockRejectedValue(
      new Error("Network error")
    );

    const { result } = renderHook(() => useRetryAttempts("run-1"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });

  it("queryKey에 runId가 포함된다 (캐시 분리 확인)", async () => {
    vi.mocked(runsApi.runsApi.getRetryAttempts).mockResolvedValue(MOCK_LIST);

    const { result: result1 } = renderHook(() => useRetryAttempts("run-A"), {
      wrapper: makeWrapper(),
    });
    const { result: result2 } = renderHook(() => useRetryAttempts("run-B"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result1.current.isLoading).toBe(false));
    await waitFor(() => expect(result2.current.isLoading).toBe(false));

    expect(runsApi.runsApi.getRetryAttempts).toHaveBeenCalledWith("run-A");
    expect(runsApi.runsApi.getRetryAttempts).toHaveBeenCalledWith("run-B");
  });
});
