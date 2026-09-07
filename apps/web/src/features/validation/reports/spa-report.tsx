"use client";

import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { SpaTStatBars } from "@/features/validation/surface-bars";
import { useT } from "@/lib/i18n";

export function asModels(
  result: Record<string, unknown>,
): Array<Record<string, unknown>> {
  return Array.isArray(result.models)
    ? (result.models as Array<Record<string, unknown>>)
    : [];
}

export function SpaReport({ run }: { run: ValidationRun }) {
  const t = useT();
  const result: Record<string, unknown> = run.result ?? {};
  const reason =
    typeof result.reason === "string" ? result.reason : null;
  const pRc =
    typeof result.p_reality_check === "number"
      ? result.p_reality_check
      : null;
  const pLower =
    typeof result.p_spa_lower === "number" ? result.p_spa_lower : null;
  const pConsistent =
    typeof result.p_spa_consistent === "number"
      ? result.p_spa_consistent
      : null;
  const pUpper =
    typeof result.p_spa_upper === "number" ? result.p_spa_upper : null;
  const nModels =
    typeof result.n_models === "number" ? result.n_models : null;
  const nObs = typeof result.n_obs === "number" ? result.n_obs : null;
  const statistic =
    typeof result.statistic === "number" ? result.statistic : null;
  const models = asModels(result);
  return (
    <Card>
      <CardHeader
        title={t("validation.reports.spa.title")}
        hint={
          <p className="text-xs text-as-muted">
            {t("validation.reports.spa.hint")}
          </p>
        }
      />
      {reason ? (
        <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p>
      ) : null}
      <p className="mb-4 text-xs text-as-muted">
        {nModels != null
          ? `${nModels} ${t("validation.reports.spa.trialsUnit")}`
          : t("validation.reports.spa.trialsUnrecorded")}
        {nObs != null ? ` · ${nObs} ${t("validation.reports.commonDays")}` : ""}
        {statistic != null ? ` · T ${statistic.toFixed(2)}` : ""}
      </p>
      <dl className="mb-4 grid gap-3 text-xs text-as-muted sm:grid-cols-4">
        <div>
          <dt>White RC</dt>
          <dd className="mt-1 tabular-nums text-as-text">
            {pRc == null ? "—" : `p ${pRc.toFixed(3)}`}
          </dd>
        </div>
        <div>
          <dt>SPA_l</dt>
          <dd className="mt-1 tabular-nums text-as-text">
            {pLower == null ? "—" : `p ${pLower.toFixed(3)}`}
          </dd>
        </div>
        <div>
          <dt>SPA_c</dt>
          <dd className="mt-1 tabular-nums text-as-text">
            {pConsistent == null ? "—" : `p ${pConsistent.toFixed(3)}`}
          </dd>
        </div>
        <div>
          <dt>SPA_u</dt>
          <dd className="mt-1 tabular-nums text-as-text">
            {pUpper == null ? "—" : `p ${pUpper.toFixed(3)}`}
          </dd>
        </div>
      </dl>
      {models.length ? (
        <SpaTStatBars
          models={models.map((row) => ({
            backtest_id:
              typeof row.backtest_id === "string" ? row.backtest_id : null,
            t_stat: typeof row.t_stat === "number" ? row.t_stat : null,
            mean: typeof row.mean === "number" ? row.mean : null,
            is_best: row.is_best === true,
          }))}
        />
      ) : null}
    </Card>
  );
}
