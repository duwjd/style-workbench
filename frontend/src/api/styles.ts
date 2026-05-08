import { client } from "./client";
import type { StyleListItem, StyleDetail } from "@/types";

export const stylesApi = {
  getAll: () =>
    client.get<StyleListItem[]>("/api/styles").then((r) => r.data),

  getById: (id: string) =>
    client.get<StyleDetail>(`/api/styles/${id}`).then((r) => r.data),

  updateStatus: (id: string, status: string) =>
    client
      .patch(`/api/styles/${id}/status`, { status })
      .then((r) => r.data),
};
