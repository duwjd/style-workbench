import { client, toCamel, deepConvert } from "./client";
import type { Run, RetryAttemptList } from "@/types";

export const runsApi = {
  create: (
    styleVersionId: string,
    userInput: Record<string, string> = {}
  ) =>
    client
      .post<Run>("/api/runs", { styleVersionId, userInput })
      .then((r) => r.data),

  getById: (id: string) =>
    client.get<Run>(`/api/runs/${id}`).then((r) => r.data),

  abort: (id: string, reason?: string) =>
    client
      .post<Run>(`/api/runs/${id}/abort`, { reason })
      .then((r) => r.data),

  /**
   * F01: Run의 모든 retry attempt 목록 조회.
   * 인터셉터가 snake→camel 변환을 처리하므로 그대로 반환.
   */
  getRetryAttempts: (runId: string) =>
    client
      .get<RetryAttemptList>(`/api/runs/${runId}/retry-attempts`)
      .then((r) => r.data),
};

// EventSource는 axios 인터셉터를 거치지 않으므로 수동으로 snake→camel 변환
function parseEvent(raw: string): unknown {
  try {
    const parsed = JSON.parse(raw);
    return deepConvert(parsed, toCamel);
  } catch {
    return raw;
  }
}

export interface RunEventCallbacks {
  onSnapshot?: (run: Run) => void;
  onNodeStarted?: (payload: { nodeId: string; nodeType: string }) => void;
  onNodeCompleted?: (payload: { nodeId: string; artifactUrl?: string }) => void;
  onNodeFailed?: (payload: { nodeId: string; error: string }) => void;
  onRunCompleted?: () => void;
  onRunFailed?: () => void;
  onRunAborted?: () => void;
  /** F01: 노드 재시도 이벤트 */
  onNodeRetry?: (payload: {
    runId: string;
    nodeId: string;
    attemptNumber: number;
    retryGuidance: Record<string, unknown>;
    failedDimensions: string[];
  }) => void;
  /** F01: 예산 초과로 Run이 중단됨 */
  onRunBudgetExceeded?: (payload: {
    runId: string;
    nodeId: string;
    totalCostWon: number;
    budgetWon: number;
  }) => void;
  onError?: (e: Event) => void;
}

/**
 * SSE 스트림 구독. 반환값은 unsubscribe 함수.
 * EventSource 연결 실패 시 onError를 호출할 뿐 화면을 깨뜨리지 않는다.
 */
export function subscribeRun(
  runId: string,
  callbacks: RunEventCallbacks
): () => void {
  const baseUrl =
    (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env
      ?.VITE_API_BASE_URL ?? "http://localhost:8000";
  const url = `${baseUrl}/api/runs/${runId}/events`;

  let es: EventSource;
  try {
    es = new EventSource(url);
  } catch {
    // EventSource 자체가 지원 안 되는 환경 — 폴링 fallback이 대신 작동
    return () => {};
  }

  es.addEventListener("snapshot", (ev: MessageEvent) => {
    const data = parseEvent(ev.data) as Run;
    callbacks.onSnapshot?.(data);
  });

  es.addEventListener("node_started", (ev: MessageEvent) => {
    const data = parseEvent(ev.data) as { nodeId: string; nodeType: string };
    callbacks.onNodeStarted?.(data);
  });

  es.addEventListener("node_completed", (ev: MessageEvent) => {
    const data = parseEvent(ev.data) as { nodeId: string; artifactUrl?: string };
    callbacks.onNodeCompleted?.(data);
  });

  es.addEventListener("node_failed", (ev: MessageEvent) => {
    const data = parseEvent(ev.data) as { nodeId: string; error: string };
    callbacks.onNodeFailed?.(data);
  });

  es.addEventListener("run_completed", () => {
    callbacks.onRunCompleted?.();
    es.close();
  });

  es.addEventListener("run_failed", () => {
    callbacks.onRunFailed?.();
    es.close();
  });

  es.addEventListener("run_aborted", () => {
    callbacks.onRunAborted?.();
    es.close();
  });

  // F01: 신규 SSE 이벤트 핸들러
  es.addEventListener("node_retry", (ev: MessageEvent) => {
    const data = parseEvent(ev.data) as {
      runId: string;
      nodeId: string;
      attemptNumber: number;
      retryGuidance: Record<string, unknown>;
      failedDimensions: string[];
    };
    callbacks.onNodeRetry?.(data);
  });

  es.addEventListener("run_budget_exceeded", (ev: MessageEvent) => {
    const data = parseEvent(ev.data) as {
      runId: string;
      nodeId: string;
      totalCostWon: number;
      budgetWon: number;
    };
    callbacks.onRunBudgetExceeded?.(data);
    // 예산 초과는 run_failed와 함께 오므로 스트림을 닫지 않고 run_failed에서 처리
  });

  es.onerror = (e) => {
    callbacks.onError?.(e);
    // 연결 에러 시 자동 재연결 방지 — 폴링 fallback이 담당
    es.close();
  };

  return () => es.close();
}
