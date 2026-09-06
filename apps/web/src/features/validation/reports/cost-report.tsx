"use client";

import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { CostAlphaBars } from "@/features/validation/surface-bars";
import { asPoints } from "./sensitivity-report";
import { useT } from "@/lib/i18n";

export function CostReport({ run }: { run: ValidationRun }) {
  const t = useT();
  const conclusionText =
    typeof run.result.conclusion === "string" ? run.result.conclusion : null;
  const reason =
    typeof run.result.reason === "string" ? run.result.reason : null;
  const breakeven =
    typeof run.result.breakeven_bps === "number"
      ? run.result.breakeven_bps
      : null;
  const realistic =
    typeof run.result.realistic_one_way_bps === "number"
      ? run.result.realistic_one_way_bps
      : null;
  const points = asPoints(run.result);
  return (
    <Card>
      <CardHeader
        title={t("validation.reports.cost.title")}
        hint={
          <p className="text-xs text-as-muted">
            {t("validation.reports.cost.hint")}
          </p>
        }
      />
      {conclusionText ? (
        <p className="mb-2 text-sm leading-relaxed text-as-text">
          {conclusionText}
        </p>
      ) : null}
      {reason ? (
        <p className="mb-4 text-xs leading-relaxed text-as-muted">{reason}</p>
      ) : null}
      <p className="mb-4 text-xs text-as-muted">
        {t("validation.reports.cost.breakevenLabel")}{" "}
        <span className="tabular-nums text-as-text">
          {breakeven == null
            ? t("validation.reports.cost.aboveGrid")
            : `${breakeven.toFixed(2)} bps`}
        </span>
        {realistic != null
          ? ` · ${t("validation.reports.cost.realistic")} ${realistic} bps`
          : ""}
      </p>
      {points.length ? (
        <CostAlphaBars
          points={points.map((row) => ({
            cost_bps:
              typeof row.cost_bps === "number" ? row.cost_bps : undefined,
            alpha_capm:
              typeof row.alpha_capm === "number" ? row.alpha_capm : null,
            backtest_id:
              typeof row.backtest_id === "string" ? row.backtest_id : null,
          }))}
          realisticBps={realistic}
        />
      ) : null}
    </Card>
  );
}
