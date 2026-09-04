import { create } from "zustand";
import type { TimeRange } from "@/mocks/types";

interface Toast {
  id: number;
  title: string;
  detail?: string;
}

interface AppState {
  symbol: string;
  strategyId: string;
  version: string;
  range: TimeRange;
  copilotOpen: boolean;
  paletteOpen: boolean;
  toasts: Toast[];

  setSymbol: (s: string) => void;
  setStrategy: (id: string, version?: string) => void;
  setVersion: (v: string) => void;
  setRange: (r: TimeRange) => void;
  toggleCopilot: () => void;
  setPaletteOpen: (open: boolean) => void;
  pushToast: (title: string, detail?: string) => void;
  dismissToast: (id: number) => void;
}

let toastId = 0;

export const useApp = create<AppState>((set) => ({
  symbol: "AAPL",
  strategyId: "strat-momentum-alpha",
  version: "v18",
  range: "5Y",
  copilotOpen: true,
  paletteOpen: false,
  toasts: [],

  setSymbol: (symbol) => set({ symbol }),
  setStrategy: (strategyId, version) =>
    set((s) => ({ strategyId, version: version ?? s.version })),
  setVersion: (version) => set({ version }),
  setRange: (range) => set({ range }),
  toggleCopilot: () => set((s) => ({ copilotOpen: !s.copilotOpen })),
  setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
  pushToast: (title, detail) => {
    const id = ++toastId;
    set((s) => ({ toasts: [...s.toasts, { id, title, detail }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4200);
  },
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
