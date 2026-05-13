import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import { useRunEvents } from "./useRunEvents";
import * as runsApi from "@/api/runs";

// subscribeRun mock
vi.mock("@/api/runs", () => ({
  subscribeRun: vi.fn(),
  runsApi: {},
}));

describe("useRunEvents", () => {
  let queryClient: QueryClient;
  let mockUnsubscribe: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    mockUnsubscribe = vi.fn();
    vi.mocked(runsApi.subscribeRun).mockReturnValue(mockUnsubscribe);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("runId가 없으면 subscribeRun을 호출하지 않는다", () => {
    renderHook(() => useRunEvents(undefined, queryClient, undefined));
    expect(runsApi.subscribeRun).not.toHaveBeenCalled();
  });

  it("terminal 상태면 subscribeRun을 호출하지 않는다", () => {
    renderHook(() => useRunEvents("run-1", queryClient, "succeeded"));
    expect(runsApi.subscribeRun).not.toHaveBeenCalled();
  });

  it("pending 상태면 subscribeRun을 호출한다", () => {
    renderHook(() => useRunEvents("run-1", queryClient, "pending"));
    expect(runsApi.subscribeRun).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        onSnapshot: expect.any(Function),
        onNodeCompleted: expect.any(Function),
        onNodeFailed: expect.any(Function),
        onRunCompleted: expect.any(Function),
        onRunFailed: expect.any(Function),
        onRunAborted: expect.any(Function),
      })
    );
  });

  it("status가 undefined이면 subscribeRun을 호출한다 (아직 fetch 전)", () => {
    renderHook(() => useRunEvents("run-1", queryClient, undefined));
    expect(runsApi.subscribeRun).toHaveBeenCalled();
  });

  it("onRunCompleted 콜백이 invalidateQueries를 호출한다", () => {
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    let capturedCallbacks: Parameters<typeof runsApi.subscribeRun>[1] = {};

    vi.mocked(runsApi.subscribeRun).mockImplementation((_runId, callbacks) => {
      capturedCallbacks = callbacks;
      return mockUnsubscribe;
    });

    renderHook(() => useRunEvents("run-1", queryClient, "pending"));

    capturedCallbacks.onRunCompleted?.();
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["runs", "run-1"],
    });
  });

  it("onNodeCompleted 콜백이 invalidateQueries를 호출한다", () => {
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    let capturedCallbacks: Parameters<typeof runsApi.subscribeRun>[1] = {};

    vi.mocked(runsApi.subscribeRun).mockImplementation((_runId, callbacks) => {
      capturedCallbacks = callbacks;
      return mockUnsubscribe;
    });

    renderHook(() => useRunEvents("run-1", queryClient, "pending"));

    capturedCallbacks.onNodeCompleted?.({ nodeId: "n1" });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["runs", "run-1"],
    });
  });

  it("언마운트 시 unsubscribe를 호출한다", () => {
    const { unmount } = renderHook(() =>
      useRunEvents("run-1", queryClient, "pending")
    );
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalled();
  });
});
