"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CircleCheck, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api, type RiskSummary } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { MetricTile } from "@/components/ui/metric-tile";

function money(value: number | null | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function percent(value: number | null | undefined) {
  if (value == null) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

const reasonKeys: Record<string, string> = {
  strategy_not_paper_ready: "risk.strategyNotPaperReady",
  risk_limits_invalid: "risk.riskLimitsInvalid",
  paper_account_missing: "risk.paperAccountMissing",
  paper_reconciliation_not_matched: "risk.reconciliationNotMatched",
};

export function RiskDesk() {
  const t = useT();
  const [selectedId, setSelectedId] = useState("");
  const strategies = useQuery({ queryKey: ["risk-strategies"], queryFn: api.listStrategies });
  const monitorable = strategies.data ?? [];
  const strategyId = selectedId || monitorable[0]?.id;
  const summary = useQuery({
    queryKey: ["risk-summary", strategyId],
    queryFn: () => api.getSummary(strategyId!),
    enabled: Boolean(strategyId),
  });

  if (strategies.isLoading) {
    return <div className="h-80 animate-pulse rounded-as bg-as-secondary" />;
  }
  if (strategies.isError) {
    return <Card><p className="text-sm text-as-negative">{t("risk.noStrategies")}</p></Card>;
  }
  if (!monitorable.length) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("risk.title")} description={t("risk.description")} />
        <Card><EmptyState title={t("risk.noStrategies")} description={t("risk.noStrategiesDescription")} /></Card>
      </div>
    );
  }

  const data = summary.data;
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("risk.title")}
        description={t("risk.description")}
        action={
          <label className="flex items-center gap-2 text-sm text-as-muted">
            <span>{t("risk.strategy")}</span>
            <select
              aria-label={t("risk.strategy")}
              value={strategyId}
              onChange={(event) => setSelectedId(event.target.value)}
              className="rounded-lg border border-as-border bg-as-bg px-3 py-2 text-sm text-as-text outline-none focus:border-as-primary"
            >
              {monitorable.map((strategy) => <option key={strategy.id} value={strategy.id}>{strategy.name}</option>)}
            </select>
          </label>
        }
      />

      {summary.isLoading ? <div className="h-48 animate-pulse rounded-as bg-as-secondary" /> : null}
      {summary.isError ? <Card><p className="text-sm text-as-negative">{t("risk.noAccountTitle")}</p></Card> : null}
      {data ? <RiskContent data={data} t={t} /> : null}
    </div>
  );
}

function RiskContent({ data, t }: { data: RiskSummary; t: (key: string) => string }) {
  const hasAccount = data.account_available;
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title={t("risk.configTitle")} />
          <div className="flex items-start gap-3">
            {data.risk_config_valid ? <ShieldCheck className="mt-0.5 h-5 w-5 text-as-positive" /> : <AlertTriangle className="mt-0.5 h-5 w-5 text-as-negative" />}
            <div>
              <p className="font-medium text-as-text">{data.risk_config_valid ? t("risk.configValid") : t("risk.configInvalid")}</p>
              {data.risk_limits ? <dl className="mt-4 grid gap-3 text-xs">{Object.entries(data.risk_limits).filter(([, value]) => value != null).map(([key, value]) => <div key={key} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-as-border/60 pb-2"><dt className="break-all text-as-muted">{key.replace(/_/g, " ")}</dt><dd className="font-medium tabular text-as-text">{String(value)}</dd></div>)}</dl> : <p className="mt-2 text-xs text-as-muted">{t("risk.noConfig")}</p>}
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title={t("risk.reconciliationTitle")} />
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-as-muted">{data.reconciliation_status || t("risk.unavailable")}</span>
            <Badge tone={data.reconciliation_status === "MATCHED" ? "green" : "amber"}>
              {data.reconciliation_status === "MATCHED" ? t("risk.matched") : t("risk.unavailable")}
            </Badge>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title={t("risk.accountTitle")} />
        {hasAccount ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <MetricTile label={t("risk.initialCapital")} value={money(data.initial_capital)} />
            <MetricTile label={t("risk.cash")} value={money(data.cash)} />
            <MetricTile label={t("risk.equity")} value={money(data.equity)} />
            <MetricTile label={t("risk.grossExposure")} value={percent(data.gross_exposure)} />
            <MetricTile label={t("risk.netExposure")} value={percent(data.net_exposure)} />
          </div>
        ) : (
          <EmptyState title={t("risk.noAccountTitle")} description={t("risk.noAccountDescription")} />
        )}
      </Card>

      <Card>
        <CardHeader title={t("risk.blockersTitle")} />
        {data.blocking_reasons?.length ? (
          <div className="space-y-2">
            {data.blocking_reasons.map((reason) => <div key={reason} className="flex items-center gap-2 text-sm text-as-negative"><AlertTriangle className="h-4 w-4" />{t(reasonKeys[reason] || reason)}</div>)}
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-as-positive"><CircleCheck className="h-4 w-4" />{t("risk.noBlockers")}</div>
        )}
      </Card>
    </>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return <div><p className="text-sm font-medium text-as-text">{title}</p><p className="mt-1 text-sm leading-relaxed text-as-muted">{description}</p></div>;
}
