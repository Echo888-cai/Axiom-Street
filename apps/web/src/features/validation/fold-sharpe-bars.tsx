function widthPct(value: number, maxAbs: number): number {
  if (maxAbs <= 0) return 8;
  return Math.max(8, Math.min(100, (Math.abs(value) / maxAbs) * 100));
}

export function FoldSharpeBars({ folds }: { folds: Array<Record<string, unknown>> }) {
  const maxAbs = Math.max(
    0.5,
    ...folds.flatMap((fold) => [
      Math.abs(Number(fold.is_sharpe) || 0),
      Math.abs(Number(fold.oos_sharpe) || 0),
    ]),
  );

  return (
    <div className="space-y-3">
      {folds.map((fold, i) => {
        const isSharpe = Number(fold.is_sharpe) || 0;
        const oosSharpe = Number(fold.oos_sharpe) || 0;
        const oosTone = oosSharpe < 0 ? "bg-as-negative" : "bg-as-positive";
        const oosYear = String(fold.oos_start || "").slice(0, 4);
        return (
          <div
            key={`${fold.index ?? i}-${String(fold.oos_start ?? i)}`}
            className="grid gap-2 sm:grid-cols-[7.5rem_1fr] sm:items-center"
          >
            <div className="text-[11px] text-as-muted">
              <div className="font-medium text-as-text">第 {Number(fold.index ?? i) + 1} 折</div>
              <div className="tabular-nums">{oosYear || "—"} OOS</div>
            </div>
            <div className="space-y-1.5">
              <Bar label="IS" value={isSharpe} width={widthPct(isSharpe, maxAbs)} className="bg-as-primary" />
              <Bar label="OOS" value={oosSharpe} width={widthPct(oosSharpe, maxAbs)} className={oosTone} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Bar({
  label,
  value,
  width,
  className,
}: {
  label: string;
  value: number;
  width: number;
  className: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-8 shrink-0 text-[10px] uppercase tracking-wide text-as-muted">{label}</span>
      <div className="h-2 flex-1 rounded-full bg-as-secondary">
        <div className={`h-2 rounded-full ${className}`} style={{ width: `${width}%` }} />
      </div>
      <span className="w-14 shrink-0 text-right text-xs tabular-nums text-as-text">
        {value.toFixed(2)}
      </span>
    </div>
  );
}
