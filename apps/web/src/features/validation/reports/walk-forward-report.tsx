import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { EquityCurve } from "@/components/charts/equity-curve";
import { FoldSharpeBars } from "@/features/validation/fold-sharpe-bars";

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
  const folds = asFolds(run.result);
  const equity = asEquity(run.result);
  const combined =
    typeof run.result.combined_oos_sharpe === "number"
      ? run.result.combined_oos_sharpe
      : null;
  const reason =
    typeof run.result.reason === "string" ? run.result.reason : null;
  return (
    <Card>
      <CardHeader
        title="最近一次 Walk-forward"
        hint={
          <p className="text-xs text-as-muted">
            {run.params.mode === "anchored" ? "锚定" : "滚动"} · 训练{" "}
            {String(run.params.train_years ?? "—")} 年 / 测试{" "}
            {String(run.params.test_years ?? "—")} 年
          </p>
        }
      />
      {reason ? (
        <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p>
      ) : null}
      {combined != null ? (
        <p className="mb-4 text-xs text-as-muted">
          拼接样本外 Sharpe{" "}
          <span className="tabular-nums text-as-text">
            {combined.toFixed(2)}
          </span>
          {run.result.overfit_collapse === true ? " · 判定为过拟合塌缩" : ""}
        </p>
      ) : null}
      {folds.length ? <FoldSharpeBars folds={folds} /> : null}
      {equity.length ? (
        <div className="mt-6">
          <h4 className="mb-2 text-xs font-medium text-as-muted">
            拼接样本外净值
          </h4>
          <EquityCurve data={equity} height={220} />
        </div>
      ) : null}
    </Card>
  );
}
