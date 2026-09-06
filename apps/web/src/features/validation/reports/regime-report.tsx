"use client";

import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { RegimeSharpeBars } from "@/features/validation/surface-bars";
import { useT } from "@/lib/i18n";

export function asSlices(
  result: Record<string, unknown>,
): Array<Record<string, unknown>> {
  return Array.isArray(result.slices)
    ? (result.slices as Array<Record<string, unknown>>)
    : [];
}

export function RegimeReport({ run }: { run: ValidationRun }) {
  const t = useT();
  const reason =
    typeof run.result.reason === "string" ? run.result.reason : null;
  const concentrated =
    typeof run.result.concentrated_in === "string"
      ? run.result.concentrated_in
      : null;
  const slices = asSlices(run.result);
  return (
    <Card>
      <CardHeader
        title={t("validation.reports.regime.title")}
        hint={
          <p className="text-xs text-as-muted">
            {t("validation.reports.regime.hint")}
          </p>
        }
      />
      {reason ? (
        <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p>
      ) : null}
      {run.result.single_regime === true ? (
        <p className="mb-4 text-xs text-as-muted">
          {t("validation.reports.regime.edgePrefix")}{" "}
          {concentrated || t("validation.reports.regime.singleRegime")}
          {t("validation.reports.regime.edgeSuffix")}
        </p>
      ) : null}
      {slices.length ? (
        <RegimeSharpeBars
          slices={slices.map((row) => ({
            key: typeof row.key === "string" ? row.key : "unknown",
            axis: typeof row.axis === "string" ? row.axis : "",
            label:
              typeof row.label === "string" ? row.label : String(row.key ?? ""),
            n_obs: typeof row.n_obs === "number" ? row.n_obs : 0,
            sharpe: typeof row.sharpe === "number" ? row.sharpe : null,
            win_rate: typeof row.win_rate === "number" ? row.win_rate : null,
            covered: row.covered === true,
          }))}
        />
      ) : null}
    </Card>
  );
}
