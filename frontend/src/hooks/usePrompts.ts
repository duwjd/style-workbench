import { useQuery } from "@tanstack/react-query";
import { promptsApi } from "@/api/prompts";
import type { PromptFilters } from "@/types/prompts";

/**
 * F05: Prompt Library 목록 조회.
 * queryKey에 filters를 포함해 필터 변경 시 자동 refetch.
 */
export function usePrompts(filters: PromptFilters = {}) {
  return useQuery({
    queryKey: ["prompts", filters],
    queryFn: () => promptsApi.list(filters),
    staleTime: 30_000,
  });
}
