import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { SpaTStatBars } from "@/features/validation/surface-bars";

export function asModels(
  result: Record<string, unknown>,
): Array<Record<string, unknown>> {
  return Array.isArray(result.models)
    ? (result.models as Array<Record<string, unknown>>)
    : [];
}

export function SpaReport({ run }: { run: ValidationRun }) {
  const reason =
    typeof run.result.reason === "string" ? run.result.reason : null;
  const pRc =
    typeof run.result.p_reality_check === "number"
      ? run.result.p_reality_check
      : null;
  const pLower =
    typeof run.result.p_spa_lower === "number" ? run.result.p_spa_lower : null;
  const pConsistent =
    typeof run.result.p_spa_consistent === "number"
      ? run.result.p_spa_consistent
      : null;
  const pUpper =
    typeof run.result.p_spa_upper === "number" ? run.result.p_spa_upper : null;
  const nModels =
    typeof run.result.n_models === "number" ? run.result.n_models : null;
  const nObs = typeof run.result.n_obs === "number" ? run.result.n_obs : null;
  const statistic =
    typeof run.result.statistic === "number" ? run.result.statistic : null;
  const models = asModels(run.result);
  return (
    <Card>
      <CardHeader
        title="最近一次 Reality Check"
        hint={
          <p className="text-xs text-as-muted">
            White RC 是未学生化的最大均值；Hansen SPA_c 是闸门。p ≥ α
            表示不能声称最好的试验优于现金。
          </p>
        }
      />
      {reason ? (
        <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p>
      ) : null}
      <p className="mb-4 text-xs text-as-muted">
        {nModels != null ? `${nModels} 条试验` : "试验数未记录"}
        {nObs != null ? ` · ${nObs} 个共同交易日` : ""}
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
