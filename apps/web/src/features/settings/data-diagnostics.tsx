export function ReconcileReports({
  reports,
  source,
  ready,
}: {
  reports?: Array<{
    symbol?: string;
    primary_source?: string;
    secondary_source?: string;
    compared_bars?: number;
    suspect_bars?: number;
    issues?: Array<{
      rule: string;
      severity: string;
      message: string;
      examples?: string[];
    }>;
  }>;
  source?: string | null;
  ready: boolean;
}) {
  const hasReports = Boolean(reports && reports.length > 0);
  if (!hasReports && !ready) return null;
  if (!hasReports) {
    return (
      <p className="mt-3 text-[11px] text-as-muted">
        尚未做双源对账。有 POLYGON_API_KEY 时默认会对账
        yfinance；也可在摄取时指定 reconcile_with。close 偏差超过 10 bps 的 bar
        会列在这里。
      </p>
    );
  }
  return (
    <div className="mt-4 rounded-as border border-as-border bg-as-secondary px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-as-text">
        双源对账{source ? `（对账源 ${source}）` : ""}
      </div>
      <ul className="space-y-2 text-as-muted">
        {(reports || []).map((row, index) => (
          <li key={`${row.symbol || "row"}-${index}`}>
            <span className="text-as-text tabular-nums">
              {row.symbol || "—"} · 对比 {row.compared_bars ?? 0} 根 · 可疑{" "}
              {row.suspect_bars ?? 0} 根
            </span>
            {(row.issues || []).map((issue) => (
              <p key={`${issue.rule}-${issue.severity}`} className="mt-0.5">
                {issue.severity === "blocking" ? "阻断" : "警告"} ·{" "}
                {issue.message}
                {issue.examples && issue.examples.length > 0
                  ? `（${issue.examples[0]}）`
                  : ""}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function InferredDelistings({
  rows,
  ready,
}: {
  rows?: Array<{ symbol: string; last_bar: string; effective_to: string }>;
  ready: boolean;
}) {
  if (!ready) return null;
  if (!rows || rows.length === 0) {
    return (
      <p className="mt-3 text-[11px] text-as-muted">
        最近一次摄取没有发现退市（最后一根 K 线仍在 14
        个自然日内）。开放区间的成分可在「标的池」按行情关闭。
      </p>
    );
  }
  return (
    <div className="mt-4 rounded-as border border-as-border bg-as-secondary px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-as-text">推断退市</div>
      <ul className="space-y-1 text-as-muted">
        {rows.map((row) => (
          <li key={row.symbol} className="tabular-nums">
            <span className="text-as-text">{row.symbol}</span>
            {" — 最后一根 "}
            {row.last_bar}
            {" → effective_to "}
            {row.effective_to}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function formatIngestLimits(
  cfg?: {
    max_symbols: number;
    rps: number;
    concurrency: number;
  } | null,
): string {
  if (!cfg) return "—";
  const cap = cfg.max_symbols > 0 ? `上限 ${cfg.max_symbols} 标的` : "无上限";
  const rps = cfg.rps > 0 ? `${cfg.rps} 次/秒` : "不限速";
  return `${cap} · ${rps} · 并发 ${cfg.concurrency}`;
}

export function formatReconcileCadence(
  cfg?: {
    enabled: boolean;
    interval_seconds: number;
  } | null,
): string {
  if (!cfg) return "—";
  if (!cfg.enabled) return "定时已关闭（仍可手动）";
  const seconds = cfg.interval_seconds;
  if (seconds % 86_400 === 0) {
    const days = seconds / 86_400;
    return days === 1 ? "每天自动全量再拉" : `每 ${days} 天自动全量再拉`;
  }
  if (seconds % 3_600 === 0) {
    return `每 ${seconds / 3_600} 小时自动全量再拉`;
  }
  return `每 ${seconds} 秒自动全量再拉`;
}

export function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-as-muted">{label}</dt>
      <dd className="text-right text-as-text">{value}</dd>
    </div>
  );
}
