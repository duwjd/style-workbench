/**
 * F02 — useOptimizePrompt
 *
 * POST /api/prompts/{id}/optimize mutation hook.
 * 성공(succeeded=true) 시 onSuccess 콜백 호출.
 * succeeded=false 는 200이지만 논리적 실패이므로 호출자가 직접 처리한다.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { promptsApi } from "@/api/prompts";
import type { PromptOptimizeRequest, PromptOptimizeResponse } from "@/types/prompts";

interface UseOptimizePromptOptions {
  promptId: string;
  onSuccess?: (result: PromptOptimizeResponse) => void;
  onError?: (error: unknown) => void;
}

export function useOptimizePrompt({
  promptId,
  onSuccess,
  onError,
}: UseOptimizePromptOptions) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: PromptOptimizeRequest) =>
      promptsApi.optimizePrompt(promptId, body),
    onSuccess: (result) => {
      // optimization 이력 캐시 무효화
      queryClient.invalidateQueries({
        queryKey: ["promptOptimizations", promptId],
      });
      // succeeded=true 시에만 버전 목록도 갱신 (새 버전 생성됨)
      if (result.succeeded && result.newVersionId) {
        queryClient.invalidateQueries({
          queryKey: ["promptVersions", promptId],
        });
      }
      onSuccess?.(result);
    },
    onError: (error) => {
      onError?.(error);
    },
  });
}
