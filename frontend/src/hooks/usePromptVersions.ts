import { useQuery } from "@tanstack/react-query";
import { promptsApi } from "@/api/prompts";

/**
 * F05 단계 5 — GET /api/prompts/{id}/versions 목록 조회.
 *
 * A/B 트리거 다이얼로그에서 버전 선택 목록을 채우는 데 사용한다.
 * promptId가 없으면 쿼리가 실행되지 않는다 (enabled: false).
 */
export function usePromptVersions(
  promptId: string | null | undefined,
  params?: { limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ["promptVersions", promptId, params],
    queryFn: () => promptsApi.listVersions(promptId!, params),
    enabled: !!promptId,
    staleTime: 30_000,
  });
}
