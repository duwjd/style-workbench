import { client } from "./client";
import type { Run } from "@/types";

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
};
