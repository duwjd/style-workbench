/**
 * F02 — usePromptOptimizations
 *
 * GET /api/prompts/{id}/optimizations 조회 hook.
 * OptimizationHistoryPanel 및 compare 화면에서 사용한다.
 */

import { useQuery } from "@tanstack/react-query";
import { promptsApi } from "@/api/prompts";

export function usePromptOptimizations(
  promptId: string | null | undefined,
  params?: { limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ["promptOptimizations", promptId, params],
    queryFn: () => promptsApi.listOptimizations(promptId!, params),
    enabled: !!promptId,
    staleTime: 30_000,
  });
}
