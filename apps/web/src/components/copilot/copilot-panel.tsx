"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { copilotApi } from "@/lib/api/copilot";
import type { CopilotContext } from "@/lib/api/types";
import { useT } from "@/lib/i18n";
import { parseScope, type CopilotScope } from "./scope";
import { ScopeEmpty } from "./scope-empty";
import { TrialsBlock } from "./trials-block";
import { GatesBlock } from "./gates-block";
import { InsightBlock } from "./copilot-insight";

type BadgeTone = "neutral" | "blue" | "green" | "red" | "amber";

const STRATEGY_TONES: Record<string, BadgeTone> = {
  DRAFT: "neutral",
  BACKTESTED: "blue",
  VALIDATED: "green",
  PAPER: "blue",
  APPROVED: "green",
  LIVE: "green",
  PAUSED: "amber",
  ARCHIVED: "neutral",
};

const BACKTEST_TONES: Record<string, BadgeTone> = {
  QUEUED: "neutral",
  STARTING: "amber",
  RUNNING: "amber",
  COMPLETED: "green",
  FAILED: "red",
  CANCELLED: "neutral",
};

function LoadingPanel() {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="space-y-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-5 w-3/4" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    </div>
  );
}

function PanelHeader({ context }: { context: CopilotContext }) {
  const t = useT();
  return (
    <header className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <Badge tone={STRATEGY_TONES[context.strategy_status] ?? "neutral"}>
          {context.strategy_status}
        </Badge>
        {context.latest_version != null ? (
          <span className="font-mono text-[10.5px] tabular-nums text-as-muted">
            {t("copilot.version")} {context.latest_version}
          </span>
        ) : null}
      </div>
      <h1 className="truncate text-[15px] font-semibold tracking-[-.01em] text-as-text">
        {context.strategy_name}
      </h1>
      {context.backtest ? (
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-as-muted">{t("copilot.title")}</span>
          <Badge tone={BACKTEST_TONES[context.backtest.status] ?? "neutral"}>
            {context.backtest.status}
          </Badge>
        </div>
      ) : null}
    </header>
  );
}

function ScopedContext({ scope }: { scope: CopilotScope }) {
  const t = useT();
  const query = useQuery({
    queryKey: ["copilot-context", scope.resource, scope.id],
    queryFn: () => copilotApi.getContext(scope.resource, scope.id),
    staleTime: 30_000,
  });

  if (query.isLoading) return <LoadingPanel />;
  if (query.isError || !query.data) return <ScopeEmpty variant="not-found" />;
  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <PanelHeader context={query.data} />
      <div className="min-h-0 flex-1 space-y-5">
        <TrialsBlock rows={query.data.by_snapshot ?? []} total={query.data.total_trials ?? 0} />
        <GatesBlock gates={query.data.gates ?? []} />
        <InsightBlock
          resource={scope.resource}
          id={scope.id}
          strategyId={query.data.strategy_id}
          providerEnabled={query.data.provider?.enabled ?? false}
          providerName={query.data.provider?.name ?? ""}
        />
      </div>
      <p className="border-t border-as-border pt-3 text-[10.5px] leading-relaxed text-as-muted">
        {t("copilot.subtitle")}
      </p>
    </div>
  );
}

export function CopilotPanel() {
  const pathname = usePathname();
  const scope = parseScope(pathname);
  return (
    <aside
      className="hidden w-80 shrink-0 overflow-y-auto border-l border-as-border xl:block"
      aria-label="copilot-context"
    >
      <div className="flex min-h-full flex-col px-4 py-5">
        {scope ? <ScopedContext scope={scope} /> : <ScopeEmpty variant="no-scope" />}
      </div>
    </aside>
  );
}
