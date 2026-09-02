"use client";

import { CheckCircle2, Info, XCircle } from "lucide-react";
import { create } from "zustand";

export type ToastTone = "ok" | "err" | "info";

type Toast = {
  id: string;
  title: string;
  tone: ToastTone;
};

type ToastStore = {
  items: Toast[];
  push: (title: string, tone?: ToastTone) => void;
  dismiss: (id: string) => void;
};

export const useToasts = create<ToastStore>((set, get) => ({
  items: [],
  push: (title, tone = "info") => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    set({ items: [...get().items, { id, title, tone }] });
    window.setTimeout(() => get().dismiss(id), 3200);
  },
  dismiss: (id) => set({ items: get().items.filter((t) => t.id !== id) }),
}));

export function toast(title: string, tone: ToastTone = "info") {
  useToasts.getState().push(title, tone);
}

export function ToastViewport() {
  const items = useToasts((s) => s.items);
  const dismiss = useToasts((s) => s.dismiss);
  if (!items.length) return null;
  return (
    <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex w-[360px] flex-col gap-2">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => dismiss(item.id)}
          className="pointer-events-auto as-scale-in flex items-start gap-3 rounded-as border border-as-border bg-as-bg px-4 py-3 text-left text-sm shadow-as-lg"
        >
          {item.tone === "ok" ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-as-positive" />
          ) : item.tone === "err" ? (
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-as-negative" />
          ) : (
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-as-primary" />
          )}
          <span className="text-as-text">{item.title}</span>
        </button>
      ))}
    </div>
  );
}
