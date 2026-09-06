"use client";

import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { SharpeSurfaceBars } from "@/features/validation/surface-bars";
import { useT } from "@/lib/i18n";

export function asPoints(
  result: Record<string, unknown>,
): Array<Record<string, unknown>> {
  return Array.isArray(result.points)
    ? (result.points as Array<Record<string, unknown>>)
    : [];
}

export function SensitivityReport({ run }: { run: ValidationRun }) {
  const t = useT();
  const reason =
    typeof run.result.reason === "string" ? run.result.reason : null;
  const shape = typeof run.result.shape === "string" ? run.result.shape : null;
  const peakSharpe =
    typeof run.result.peak_sharpe === "number" ? run.result.peak_sharpe : null;
  const width =
    typeof run.result.plateau_width === "number"
      ? run.result.plateau_width
      : null;
  const points = asPoints(run.result);
  return (
    <Card>
      <CardHeader
        title={t("validation.reports.sensitivity.title")}
        hint={
          <p className="text-xs text-as-muted">
            {t("validation.reports.sensitivity.hint")}
          </p>
        }
      />
      {reason ? (
        <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p>
      ) : null}
      <p className="mb-4 text-xs text-as-muted">
        {shape === "plateau"
          ? t("validation.shapes.plateau")
          : shape === "knife_edge"
            ? t("validation.shapes.knifeEdge")
            : t("validation.reports.sensitivity.shapeUnrecorded")}
        {peakSharpe != null
          ? ` · ${t("validation.reports.sensitivity.peakSharpePrefix")} ${peakSharpe.toFixed(2)}`
          : ""}
        {width != null
          ? ` · ${t("validation.reports.sensitivity.bandPrefix")} ${width} ${t("validation.reports.sensitivity.bandUnit")}`
          : ""}
      </p>
      {points.length ? (
        <SharpeSurfaceBars
          points={points.map((row) => ({
            value: typeof row.value === "number" ? row.value : undefined,
            sharpe: typeof row.sharpe === "number" ? row.sharpe : null,
            backtest_id:
              typeof row.backtest_id === "string" ? row.backtest_id : null,
            on_plateau: row.on_plateau === true,
            is_peak: row.is_peak === true,
          }))}
        />
      ) : null}
    </Card>
  );
}
