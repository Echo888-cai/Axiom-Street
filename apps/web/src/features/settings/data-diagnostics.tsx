"use client";

import { useT } from "@/lib/i18n";
import { Disclosure } from "@/components/ui/disclosure";

function fill(template: string, vars: Record<string, string | number>): string {
  let out = template;
  for (const [k, v] of Object.entries(vars)) {
    out = out.split(`{${k}}`).join(String(v));
  }
  return out;
}

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
  const t = useT();
  const hasReports = Boolean(reports && reports.length > 0);
  if (!hasReports && !ready) return null;
  if (!hasReports) {
    return (
      <Disclosure title="双源对账 · 尚未核验" className="mt-3">
        {t("common.diagnostics.reconcileEmpty")}
      </Disclosure>
    );
  }
  const title = source
    ? fill(t("common.diagnostics.reconcileSource"), { src: source })
    : t("common.diagnostics.reconcileTitle");
  return (
    <div className="mt-4 rounded-as border border-as-border bg-as-secondary px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-as-text">{title}</div>
      <ul className="space-y-2 text-as-muted">
        {(reports || []).map((row, index) => (
          <li key={`${row.symbol || "row"}-${index}`}>
            <span className="text-as-text tabular-nums">
              {fill(t("common.diagnostics.reconcileSummary"), {
                sym: row.symbol || "—",
                compared: row.compared_bars ?? 0,
                suspect: row.suspect_bars ?? 0,
              })}
            </span>
            {(row.issues || []).map((issue) => (
              <p key={`${issue.rule}-${issue.severity}`} className="mt-0.5">
                {issue.severity === "blocking"
                  ? t("common.blocking")
                  : t("common.warning")} · {issue.message}
                {issue.examples && issue.examples.length > 0
                  ? fill(t("common.diagnostics.issueExample"), {
                      example: issue.examples[0],
                    })
                  : null}
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
  const t = useT();
  if (!ready) return null;
  if (!rows || rows.length === 0) {
    return (
      <Disclosure title="退市检测 · 未发现异常" className="mt-3">
        {t("common.diagnostics.delistEmpty")}
      </Disclosure>
    );
  }
  return (
    <div className="mt-4 rounded-as border border-as-border bg-as-secondary px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-as-text">
        {t("common.diagnostics.delistHeader")}
      </div>
      <ul className="space-y-1 text-as-muted">
        {rows.map((row) => (
          <li key={row.symbol} className="tabular-nums">
            <span className="text-as-text">{row.symbol}</span>
            {fill(t("common.diagnostics.delistDetail"), {
              last: row.last_bar,
              to: row.effective_to,
            })}
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
  t: (key: string) => string = () => "",
): string {
  if (!cfg) return "—";
  const cap =
    cfg.max_symbols > 0
      ? fill(t("common.diagnostics.capClause"), { n: cfg.max_symbols })
      : t("common.diagnostics.noCap");
  const rps =
    cfg.rps > 0
      ? fill(t("common.diagnostics.rpsClause"), { n: cfg.rps })
      : t("common.diagnostics.unlimitedRps");
  return `${cap} · ${rps} · ${fill(t("common.diagnostics.concurrencyClause"), {
    n: cfg.concurrency,
  })}`;
}

export function formatReconcileCadence(
  cfg?: {
    enabled: boolean;
    interval_seconds: number;
  } | null,
  t: (key: string) => string = () => "",
): string {
  if (!cfg) return "—";
  if (!cfg.enabled) return t("common.diagnostics.cadenceDisabled");
  const seconds = cfg.interval_seconds;
  if (seconds % 86_400 === 0) {
    const days = seconds / 86_400;
    return days === 1
      ? t("common.diagnostics.cadenceDaily")
      : fill(t("common.diagnostics.cadenceDays"), { n: days });
  }
  if (seconds % 3_600 === 0) {
    return fill(t("common.diagnostics.cadenceHours"), {
      n: seconds / 3_600,
    });
  }
  return fill(t("common.diagnostics.cadenceSeconds"), { n: seconds });
}

export function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="shrink-0 text-as-muted">{label}</dt>
      <dd className="min-w-0 break-words text-right text-as-text">{value}</dd>
    </div>
  );
}
