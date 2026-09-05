import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { CostAlphaBars } from "@/features/validation/surface-bars";
import { asPoints } from "./sensitivity-report";

export function CostReport({ run }: { run: ValidationRun }) {
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
        title="最近一次成本敏感性"
        hint={
          <p className="text-xs text-as-muted">
            alpha_capm 归零的单边成本。不高于真实成本则策略判死。
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
        临界{" "}
        <span className="tabular-nums text-as-text">
          {breakeven == null ? "> 网格上限" : `${breakeven.toFixed(2)} bps`}
        </span>
        {realistic != null ? ` · 真实 ${realistic} bps` : ""}
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
