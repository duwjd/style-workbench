import { create } from "zustand";

interface UiState {
  selectedNodeId: string | null;
  setSelectedNodeId: (id: string | null) => void;
  theme: "dark" | "light";
  toggleTheme: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  selectedNodeId: null,
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  theme: "dark",
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      return { theme: next };
    }),
}));
