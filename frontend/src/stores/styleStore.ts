import { create } from "zustand";
import type { StyleDetail } from "@/types";

interface StyleState {
  editingStyle: StyleDetail | null;
  setEditingStyle: (s: StyleDetail | null) => void;
  dirtyDag: boolean;
  setDirtyDag: (v: boolean) => void;
}

export const useStyleStore = create<StyleState>((set) => ({
  editingStyle: null,
  setEditingStyle: (s) => set({ editingStyle: s }),
  dirtyDag: false,
  setDirtyDag: (v) => set({ dirtyDag: v }),
}));
