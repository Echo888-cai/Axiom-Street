"use client";

import Link from "next/link";
import type { BacktestMetrics } from "@/lib/api";
import { MetricTile } from "@/components/ui/metric-tile";
import { formatNumber, formatPct } from "@/lib/utils";

export function TruthStrip({
  metrics,
  pbo,
  strategyId,
}: {
  metrics: BacktestMetrics | undefined;
  pbo: number | null;
  strategyId?: string | null;
}) {
  const dsr = typeof metrics?.deflated_sharpe === "number" ? metrics.deflated_sharpe : null;
  const psr =
    typeof metrics?.probabilistic_sharpe === "number" ? metrics.probabilistic_sharpe : null;

  return (
    <section className="rounded-as border border-as-primary/20 bg-as-bg p-4 shadow-as">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium tracking-tight text-as-text">诚实指标</h2>
        <p className="text-[11px] text-as-muted">
          Deflated Sharpe 与过拟合概率排在原始夏普之前。数字来自权益序列与试验台账，不是 LEAN 自报统计。
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <MetricTile
          label="Deflated Sharpe"
          value={dsr == null ? "—" : formatPct(dsr)}
          hint={
            metrics?.dsr_n_trials != null
              ? `N=${metrics.dsr_n_trials} 次试验 · 阈值 95%`
              : "来自试验台账的多重检验修正"
          }
          tone={dsr == null ? undefined : dsr >= 0.95 ? "pos" : "neg"}
        />
        <MetricTile
          label="Probabilistic Sharpe"
          value={psr == null ? "—" : formatPct(psr)}
          hint="未做多重检验修正"
        />
        <MetricTile
          label="过拟合概率 PBO"
          value={pbo == null ? "尚未检验" : formatPct(pbo)}
          hint={
            pbo == null
              ? strategyId
                ? "需要参数扫描，不是猜测"
                : "打开验证台"
              : pbo <= 0.5
                ? "CSCV ≤ 0.5"
                : "CSCV > 0.5"
          }
          tone={pbo == null ? undefined : pbo <= 0.5 ? "pos" : "neg"}
        />
        <MetricTile
          label="试验次数"
          value={metrics?.dsr_n_trials == null ? "—" : formatNumber(metrics.dsr_n_trials, 0)}
          hint="试验台账分母，事后无法补记"
        />
        <MetricTile
          label="原始夏普"
          value={formatNumber(metrics?.sharpe)}
          hint="未校正，仅作对照"
        />
      </div>
      {strategyId ? (
        <div className="mt-3 flex flex-wrap gap-3 text-[11px]">
          <Link href="/validation" className="text-as-primary hover:underline">
            打开验证台
          </Link>
          {pbo == null ? (
            <span className="text-as-muted">PBO 空着是因为还没跑 CSCV，不是 0。</span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
