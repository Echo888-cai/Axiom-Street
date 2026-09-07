"use client";

import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { EquityCurve } from "@/components/charts/equity-curve";
import { FoldSharpeBars } from "@/features/validation/fold-sharpe-bars";
import { useT } from "@/lib/i18n";

export function asFolds(
  result: Record<string, unknown>,
): Array<Record<string, unknown>> {
  return Array.isArray(result.folds)
    ? (result.folds as Array<Record<string, unknown>>)
    : [];
}

export function asEquity(
  result: Record<string, unknown>,
): Array<{ time: string; strategy: number }> {
  const raw = Array.isArray(result.oos_equity) ? result.oos_equity : [];
  return raw
    .map((point) => {
      const row = point as { ts?: string; strategy_value?: number };
      if (!row.ts || typeof row.strategy_value !== "number") return null;
      return {
        time: String(row.ts).slice(0, 10),
        strategy: row.strategy_value,
      };
    })
    .filter(
      (point): point is { time: string; strategy: number } => point != null,
    );
}

export function WalkForwardReport({ run }: { run: ValidationRun }) {
  const t = useT();
  const result: Record<string, unknown> = run.result ?? {};
  const params: Record<string, unknown> = run.params ?? {};
  const folds = asFolds(result);
  const equity = asEquity(result);
  const combined =
    typeof result.combined_oos_sharpe === "number"
      ? result.combined_oos_sharpe
      : null;
  const reason =
    typeof result.reason === "string" ? result.reason : null;
  return (
    <Card>
      <CardHeader
        title={t("validation.reports.walkForward.title")}
        hint={
          <p className="text-xs text-as-muted">
            {`${params.mode === "anchored"
              ? t("validation.reports.walkForward.anchored")
              : t("validation.reports.walkForward.rolling")} · ${t("validation.reports.walkForward.trainLabel")} ${String(params.train_years ?? "—")} ${t("validation.reports.walkForward.yearsUnit")} / ${t("validation.reports.walkForward.testLabel")} ${String(params.test_years ?? "—")} ${t("validation.reports.walkForward.yearsUnit")}`}
          </p>
        }
      />
      {reason ? (
        <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p>
      ) : null}
      {combined != null ? (
        <p className="mb-4 text-xs text-as-muted">
          {t("validation.reports.walkForward.combinedLabel")}{" "}
          <span className="tabular-nums text-as-text">
            {combined.toFixed(2)}
          </span>
          {result.overfit_collapse === true
            ? ` · ${t("validation.reports.walkForward.collapse")}`
            : ""}
        </p>
      ) : null}
      {folds.length ? <FoldSharpeBars folds={folds} /> : null}
      {equity.length ? (
        <div className="mt-6">
          <h4 className="mb-2 text-xs font-medium text-as-muted">
            {t("validation.reports.walkForward.equityHeading")}
          </h4>
          <EquityCurve data={equity} height={220} />
        </div>
      ) : null}
    </Card>
  );
}
