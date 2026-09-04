import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { fmtPct } from "@/lib/format";
import { getSymbol } from "@/mocks/market";
import { SyntheticTag } from "@/components/ui/badge";

/**
 * Top context strip — one decision space per screen.
 * Pages compose their own context (symbol, range, strategy, actions).
 */
export function ContextBar({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-11 shrink-0 items-center gap-3 border-b border-edge bg-bg pr-3.5 pl-4">
      {children}
    </div>
  );
}

export function ContextDivider() {
  return <span className="h-4 w-px shrink-0 bg-edge-strong" />;
}

export function ContextLabel({ children }: { children: ReactNode }) {
  return <span className="shrink-0 text-[11px] text-text-3">{children}</span>;
}

/** Symbol anchor for the context bar: ticker, name, live-ish price. */
export function SymbolContext({ symbol }: { symbol: string }) {
  const info = getSymbol(symbol);
  const up = info.changePct >= 0;
  return (
    <div className="flex min-w-0 items-baseline gap-2">
      <span className="mono text-[13px] font-semibold text-text">{info.symbol}</span>
      <span className="truncate text-[11px] text-text-3">{info.name}</span>
      <span className="mono text-[12px] text-text-2">${info.price.toFixed(2)}</span>
      <span className={cn("mono text-[11px]", up ? "text-pos" : "text-neg")}>
        {fmtPct(info.changePct)}
      </span>
    </div>
  );
}

/** Right-aligned slot cluster */
export function ContextActions({ children }: { children: ReactNode }) {
  return <div className="ml-auto flex shrink-0 items-center gap-2">{children}</div>;
}

export function HonestyMarker() {
  return <SyntheticTag />;
}
