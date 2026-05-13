import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";
import { promptsApi } from "@/api/prompts";

/**
 * F05: 단건 Prompt 조회. ETag를 ref에 보관해 mutation에서 재사용 가능하도록 함.
 */
export function usePrompt(id: string | undefined) {
  const etagRef = useRef<string>("");

  const query = useQuery({
    queryKey: ["prompts", id],
    queryFn: async () => {
      const result = await promptsApi.getById(id!);
      etagRef.current = result.etag;
      return result.data;
    },
    enabled: !!id,
    staleTime: 30_000,
  });

  return { ...query, etagRef };
}
