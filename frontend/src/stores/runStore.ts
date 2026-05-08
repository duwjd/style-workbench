import { create } from "zustand";

interface RunState {
  activeRunIds: string[];
  addRunId: (id: string) => void;
  removeRunId: (id: string) => void;
}

export const useRunStore = create<RunState>((set) => ({
  activeRunIds: [],
  addRunId: (id) =>
    set((s) => ({ activeRunIds: [...s.activeRunIds, id] })),
  removeRunId: (id) =>
    set((s) => ({
      activeRunIds: s.activeRunIds.filter((r) => r !== id),
    })),
}));
