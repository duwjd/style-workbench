import { useQuery } from "@tanstack/react-query";
import { runsApi } from "@/api/runs";
import type { RetryAttemptList } from "@/types";

/**
 * F01: Run의 retry attempt 목록을 조회하는 TanStack Query hook.
 *
 * - runId가 없으면 쿼리하지 않는다.
 * - 30초마다 자동 refetch (실행 중 실시간 업데이트는 SSE invalidate가 담당).
 */
export function useRetryAttempts(
  runId: string | undefined
): {
  data: RetryAttemptList | undefined;
  isLoading: boolean;
  isError: boolean;
} {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["retryAttempts", runId],
    queryFn: () => runsApi.getRetryAttempts(runId!),
    enabled: !!runId,
    staleTime: 30_000,
  });

  return { data, isLoading, isError };
}
