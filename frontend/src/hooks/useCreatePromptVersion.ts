import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { promptsApi } from "@/api/prompts";
import { PreconditionFailedError } from "@/types/prompts";
import type { PromptVersionCreateBody } from "@/types/prompts";

interface Options {
  promptId: string;
  etagRef: React.MutableRefObject<string>;
  onSuccess?: () => void;
}

/**
 * F05: 새 버전 생성 mutation. ETag 불일치(412) 시 별도 알림.
 */
export function useCreatePromptVersion({ promptId, etagRef, onSuccess }: Options) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: PromptVersionCreateBody) =>
      promptsApi.createVersion(promptId, body, etagRef.current),
    onSuccess: (result) => {
      if (result.warnings.length > 0) {
        toast.warning(`버전 저장됨 (경고 ${result.warnings.length}건): ${result.warnings[0]}`);
      } else {
        toast.success("새 버전이 저장되었습니다.");
      }
      queryClient.invalidateQueries({ queryKey: ["prompts", promptId] });
      onSuccess?.();
    },
    onError: (e) => {
      if (e instanceof PreconditionFailedError) {
        toast.error(e.message);
      } else {
        toast.error("버전 저장에 실패했습니다.");
      }
    },
  });
}
