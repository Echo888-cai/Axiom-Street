"use client";

import Link from "next/link";
import type { BacktestMetrics } from "@/lib/api";
import { MetricTile } from "@/components/ui/metric-tile";
import { formatNumber, formatPct } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export function TruthStrip({
  metrics,
  pbo,
  strategyId,
}: {
  metrics: BacktestMetrics | undefined;
  pbo: number | null;
  strategyId?: string | null;
}) {
  const t = useT();
  const dsr = typeof metrics?.deflated_sharpe === "number" ? metrics.deflated_sharpe : null;
  const psr =
    typeof metrics?.probabilistic_sharpe === "number" ? metrics.probabilistic_sharpe : null;

  return (
    <section className="rounded-as border border-as-primary/20 bg-as-bg p-4 shadow-as">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium tracking-tight text-as-text">{t("tearsheet.truth.title")}</h2>
        <p className="text-[11px] text-as-muted">
          {t("tearsheet.truth.blurb")}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <MetricTile
          label="Deflated Sharpe"
          value={dsr == null ? "—" : formatPct(dsr)}
          hint={
            metrics?.dsr_n_trials != null
              ? t("tearsheet.truth.dsrHint").replace("{n}", String(metrics.dsr_n_trials))
              : t("tearsheet.truth.dsrNoTrialsHint")
          }
          tone={dsr == null ? undefined : dsr >= 0.95 ? "pos" : "neg"}
        />
        <MetricTile
          label="Probabilistic Sharpe"
          value={psr == null ? "—" : formatPct(psr)}
          hint={t("tearsheet.truth.psrHint")}
        />
        <MetricTile
          label={t("tearsheet.truth.pboLabel")}
          value={pbo == null ? t("tearsheet.truth.pboNotRun") : formatPct(pbo)}
          hint={
            pbo == null
              ? strategyId
                ? t("tearsheet.truth.pboNeedsScan")
                : t("tearsheet.truth.openValidation")
              : pbo <= 0.5
                ? "CSCV ≤ 0.5"
                : "CSCV > 0.5"
          }
          tone={pbo == null ? undefined : pbo <= 0.5 ? "pos" : "neg"}
        />
        <MetricTile
          label={t("tearsheet.truth.trialsLabel")}
          value={metrics?.dsr_n_trials == null ? "—" : formatNumber(metrics.dsr_n_trials, 0)}
          hint={t("tearsheet.truth.trialsHint")}
        />
        <MetricTile
          label={t("tearsheet.truth.rawSharpeLabel")}
          value={formatNumber(metrics?.sharpe)}
          hint={t("tearsheet.truth.rawSharpeHint")}
        />
      </div>
      {strategyId ? (
        <div className="mt-3 flex flex-wrap gap-3 text-[11px]">
          <Link href="/validation" className="text-as-primary hover:underline">
            {t("tearsheet.truth.openValidation")}
          </Link>
          {pbo == null ? (
            <span className="text-as-muted">{t("tearsheet.truth.pboEmptyNote")}</span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
