import { useEffect } from "react";
import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { subscribeRun } from "@/api/runs";

const TERMINAL_STATUSES = new Set(["succeeded", "failed", "aborted"]);

/**
 * SSE 기반 run 이벤트 구독 훅.
 *
 * - runId가 없거나 run이 이미 terminal 상태면 구독하지 않는다.
 * - node_completed / run_completed / run_failed / run_aborted 수신 시
 *   ["runs", runId] 쿼리를 invalidate해 UI를 즉시 갱신한다.
 * - EventSource 연결 실패 시 조용히 종료 — 폴링(refetchInterval)이 fallback으로 동작.
 */
export function useRunEvents(
  runId: string | undefined,
  queryClient: QueryClient,
  currentStatus: string | undefined
) {
  useEffect(() => {
    if (!runId) return;
    // 이미 terminal 상태면 스트림 불필요
    if (currentStatus && TERMINAL_STATUSES.has(currentStatus)) return;

    const invalidate = () => {
      queryClient.invalidateQueries({ queryKey: ["runs", runId] });
    };

    const unsubscribe = subscribeRun(runId, {
      onSnapshot: () => {
        // 스냅샷 수신 시에도 최신 데이터로 동기화
        invalidate();
      },
      onNodeCompleted: () => {
        invalidate();
      },
      onNodeFailed: () => {
        invalidate();
      },
      onRunCompleted: () => {
        invalidate();
      },
      onRunFailed: () => {
        invalidate();
      },
      onRunAborted: () => {
        invalidate();
      },
      // F01: 재시도 이벤트 — retry timeline 갱신 + 토스트
      onNodeRetry: (payload) => {
        queryClient.invalidateQueries({ queryKey: ["retryAttempts", runId] });
        toast.info(
          `재시도 #${payload.attemptNumber}: 노드 ${payload.nodeId}`
        );
      },
      // F01: 예산 초과 이벤트 — 에러 토스트 (spec §7.3)
      onRunBudgetExceeded: (payload) => {
        const total = Number(payload.totalCostWon).toLocaleString("ko-KR");
        const budget = Number(payload.budgetWon).toLocaleString("ko-KR");
        toast.error(
          `예산 초과: ${total}원 / 한도 ${budget}원 — Run 중단됨`,
          { duration: 8_000 }
        );
      },
      // onError: EventSource 실패는 subscribeRun 내부에서 es.close() 후 조용히 종료.
      // 화면을 깨뜨리지 않는다. 폴링이 계속 동작한다.
    });

    return unsubscribe;
  }, [runId, queryClient, currentStatus]);
}
