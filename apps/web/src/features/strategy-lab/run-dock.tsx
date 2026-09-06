"use client";

import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { api, type Backtest } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ProgressSteps } from "@/components/ui/progress-steps";
import { useT } from "@/lib/i18n";
import { labelStatus, labelStep } from "@/lib/labels";
import { formatNumber } from "@/lib/utils";

export function RunDock({
  backtestId,
  onDismiss,
  onFailure,
}: {
  backtestId: string;
  onDismiss: () => void;
  onFailure?: (error: { message?: string; line?: number }) => void;
}) {
  const t = useT();
  const runSteps = [
    t("strategy.runStepQueued"),
    t("strategy.runStepPreparing"),
    t("strategy.runStepLoading"),
    t("strategy.runStepRunning"),
    t("strategy.runStepMetrics"),
  ];
  const failureRef = useRef(onFailure);
  useEffect(() => {
    failureRef.current = onFailure;
  }, [onFailure]);
  const [bt, setBt] = useState<Backtest | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function pull() {
      const row = await api.getBacktest(backtestId);
      if (!cancelled) setBt(row);
      if (row.status === "FAILED" && row.error) failureRef.current?.(row.error);
    }
    pull().catch(() => {
      /* Event stream reconnect will retry. */
    });
    const es = new EventSource(api.eventsUrl(backtestId));
    es.addEventListener("progress", (ev) => {
      try {
        const payload = JSON.parse(
          (ev as MessageEvent).data,
        ) as Partial<Backtest> & {
          progress_step?: string;
          status?: string;
        };
        setBt((prev) =>
          prev
            ? {
                ...prev,
                status: payload.status || prev.status,
                progress_step: payload.progress_step || prev.progress_step,
              }
            : prev,
        );
      } catch {
        /* heartbeat */
      }
    });
    es.addEventListener("done", () => {
      es.close();
      pull().catch(() => {
        /* Keep the last known state. */
      });
    });
    return () => {
      cancelled = true;
      es.close();
    };
  }, [backtestId]);

  if (!bt) return null;
  const running = ["QUEUED", "STARTING", "RUNNING"].includes(bt.status);
  const step = labelStep(bt.progress_step) || labelStatus(bt.status);

  return (
    <div className="rounded-as border border-as-border bg-as-bg px-4 py-3 shadow-as as-enter">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-medium text-as-text">
            {running ? (
              <>
                <span className="h-1.5 w-1.5 rounded-full bg-as-primary as-live-dot" />
                {t("strategy.dockRunningTitle")}
              </>
            ) : bt.status === "COMPLETED" ? (
              t("strategy.dockCompletedTitle")
            ) : (
              labelStatus(bt.status)
            )}
            {!running && bt.sharpe != null ? (
              <span className="text-[11px] font-normal tabular text-as-muted">
                {t("strategy.sharpeLabel")} {formatNumber(bt.sharpe)}
              </span>
            ) : null}
          </div>
          {running ? (
            <div className="mt-2 max-w-xl">
              <ProgressSteps
                steps={runSteps}
                current={step || t("strategy.runStepQueued")}
              />
            </div>
          ) : bt.status === "FAILED" ? (
            <p className="mt-1 text-xs text-as-negative">
              {bt.error?.message || t("strategy.dockFailed")}
            </p>
          ) : (
            <p className="mt-1 text-xs text-as-muted">
              {t("strategy.dockHint")}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/backtests/${backtestId}`}>
            <Button
              size="sm"
              variant={bt.status === "COMPLETED" ? "primary" : "secondary"}
            >
              {t("strategy.openTearsheet")}
            </Button>
          </Link>
          <Button size="sm" variant="ghost" onClick={onDismiss}>
            {t("strategy.collapseDock")}
          </Button>
        </div>
      </div>
    </div>
  );
}
