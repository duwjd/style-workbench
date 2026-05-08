import { client } from "./client";
import type { StyleSummary } from "@/types";

export interface BriefPayload {
  concept: string;
  vertical: string;
  tone: string;
  stepComposition: string[];
  inputKinds: string[];
  n: number;
}

export const variantsApi = {
  generate: (brief: BriefPayload) =>
    client
      .post<StyleSummary[]>("/api/variants", brief)
      .then((r) => r.data),
};
