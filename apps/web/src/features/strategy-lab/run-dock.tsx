"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Backtest } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ProgressSteps } from "@/components/ui/progress-steps";
import { labelStatus, labelStep } from "@/lib/labels";
import { formatNumber } from "@/lib/utils";

const RUN_STEPS = ["排队中", "准备环境", "加载数据", "运行策略", "计算指标"];

export function RunDock({
  backtestId,
  onDismiss,
  onFailure,
}: {
  backtestId: string;
  onDismiss: () => void;
  onFailure?: (error: { message?: string; line?: number }) => void;
}) {
  const [bt, setBt] = useState<Backtest | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function pull() {
      const row = await api.getBacktest(backtestId);
      if (!cancelled) setBt(row);
      if (row.status === "FAILED" && row.error) onFailure?.(row.error);
    }
    pull();
    const es = new EventSource(api.eventsUrl(backtestId));
    es.addEventListener("progress", (ev) => {
      try {
        const payload = JSON.parse((ev as MessageEvent).data) as Partial<Backtest> & {
          progress_step?: string;
          status?: string;
        };
        setBt((prev) =>
          prev
            ? { ...prev, status: payload.status || prev.status, progress_step: payload.progress_step || prev.progress_step }
            : prev,
        );
      } catch {
        /* heartbeat */
      }
    });
    es.addEventListener("done", () => {
      es.close();
      pull();
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
                回测进行中
              </>
            ) : bt.status === "COMPLETED" ? (
              "回测完成"
            ) : (
              labelStatus(bt.status)
            )}
            {!running && bt.sharpe != null ? (
              <span className="text-[11px] font-normal tabular text-as-muted">
                夏普 {formatNumber(bt.sharpe)}
              </span>
            ) : null}
          </div>
          {running ? (
            <div className="mt-2 max-w-xl">
              <ProgressSteps steps={RUN_STEPS} current={step || "排队中"} />
            </div>
          ) : bt.status === "FAILED" ? (
            <p className="mt-1 text-xs text-as-negative">{bt.error?.message || "回测失败"}</p>
          ) : (
            <p className="mt-1 text-xs text-as-muted">留在实验室继续改，或打开 tearsheet。</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/backtests/${backtestId}`}>
            <Button size="sm" variant={bt.status === "COMPLETED" ? "primary" : "secondary"}>
              打开 tearsheet
            </Button>
          </Link>
          <Button size="sm" variant="ghost" onClick={onDismiss}>
            收起
          </Button>
        </div>
      </div>
    </div>
  );
}
