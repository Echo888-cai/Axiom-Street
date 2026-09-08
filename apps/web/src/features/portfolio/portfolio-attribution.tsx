"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BarChart3, Layers3 } from "lucide-react";
import { useState } from "react";
import { api, type PortfolioAttribution as AttributionRow } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

function formatWeight(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function attributionTone(value: number): "green" | "red" | "neutral" {
  if (value > 0) return "green";
  if (value < 0) return "red";
  return "neutral";
}

function latestAttribution(rows: AttributionRow[] | undefined) {
  return rows?.[0] ?? null;
}

export function PortfolioAttribution() {
  const t = useT();
  const [selectedId, setSelectedId] = useState("");
  const portfolios = useQuery({
    queryKey: ["portfolios"],
    queryFn: api.listPortfolios,
  });
  const portfolioId = selectedId || portfolios.data?.[0]?.id;
  const allocations = useQuery({
    queryKey: ["portfolio-allocations", portfolioId],
    queryFn: () => api.listPortfolioAllocations(portfolioId!),
    enabled: Boolean(portfolioId),
  });
  const attribution = useQuery({
    queryKey: ["portfolio-attribution", portfolioId],
    queryFn: () => api.listPortfolioAttribution(portfolioId!),
    enabled: Boolean(portfolioId),
  });

  if (portfolios.isLoading) {
    return <div className="h-80 animate-pulse rounded-as bg-as-secondary" />;
  }

  if (portfolios.isError) {
    return (
      <Card>
        <div className="flex items-start gap-3 text-as-negative">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <h2 className="font-semibold">{t("portfolio.loadErrorTitle")}</h2>
            <p className="mt-1 text-sm text-as-muted">
              {t("portfolio.loadErrorDescription")}
            </p>
          </div>
        </div>
      </Card>
    );
  }

  if (!portfolios.data?.length) {
    return (
      <div className="space-y-6">
        <PageHeader
          title={t("portfolio.title")}
          description={t("portfolio.description")}
        />
        <Card>
          <div className="flex items-start gap-3">
            <Layers3 className="mt-0.5 h-5 w-5 text-as-primary" />
            <div>
              <h2 className="font-semibold text-as-text">
                {t("portfolio.emptyTitle")}
              </h2>
              <p className="mt-1 text-sm text-as-muted">
                {t("portfolio.emptyDescription")}
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  const portfolio =
    portfolios.data.find((item) => item.id === portfolioId) ?? portfolios.data[0];
  const latest = latestAttribution(attribution.data);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("portfolio.title")}
        description={t("portfolio.description")}
        action={
          <label className="flex items-center gap-2 text-sm text-as-muted">
            <span className="sr-only">{t("portfolio.selectLabel")}</span>
            <select
              aria-label={t("portfolio.selectLabel")}
              value={portfolio.id}
              onChange={(event) => setSelectedId(event.target.value)}
              className="rounded-lg border border-as-border bg-as-bg px-3 py-2 text-sm text-as-text outline-none focus:border-as-primary"
            >
              {portfolios.data.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader
            title={t("portfolio.allocationTitle")}
            hint={<Badge tone="blue">{portfolio.base_currency}</Badge>}
          />
          {allocations.isLoading ? (
            <div className="h-24 animate-pulse rounded-lg bg-as-secondary" />
          ) : allocations.data?.length ? (
            <div className="space-y-3">
              {allocations.data.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between gap-3 border-b border-as-border pb-3 last:border-0 last:pb-0"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-as-text">
                      {t("portfolio.strategyPrefix")} {item.strategy_id.slice(0, 8)}
                    </p>
                    <p className="mt-0.5 text-xs text-as-muted">
                      {item.effective_from}
                    </p>
                  </div>
                  <span className="text-sm font-semibold text-as-text">
                    {formatWeight(item.weight)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-as-muted">{t("portfolio.noAllocations")}</p>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title={t("portfolio.attributionTitle")}
            hint={
              latest ? (
                <span className="text-xs text-as-muted">
                  {t("portfolio.asOf")} {latest.as_of}
                </span>
              ) : undefined
            }
          />
          {attribution.isLoading ? (
            <div className="h-24 animate-pulse rounded-lg bg-as-secondary" />
          ) : latest ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric label={t("portfolio.portfolioReturn")} value={latest.portfolio_return} />
              <Metric label={t("portfolio.benchmarkReturn")} value={latest.benchmark_return} />
              <Metric label={t("portfolio.activeReturn")} value={latest.active_return} />
              <Metric label={t("portfolio.allocationEffect")} value={latest.allocation_effect} />
              <Metric label={t("portfolio.selectionEffect")} value={latest.selection_effect} />
              <Metric label={t("portfolio.interactionEffect")} value={latest.interaction_effect} />
            </div>
          ) : (
            <p className="text-sm text-as-muted">{t("portfolio.noAttribution")}</p>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader
          title={t("portfolio.factorTitle")}
          hint={<Badge tone="amber">{t("portfolio.notAvailableBadge")}</Badge>}
        />
        <div className="flex items-start gap-3">
          <BarChart3 className="mt-0.5 h-5 w-5 shrink-0 text-[var(--as-warning)]" />
          <p className="text-sm leading-relaxed text-as-muted">
            {t("portfolio.factorDescription")}
          </p>
        </div>
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-as-border bg-as-secondary/40 p-3">
      <p className="text-xs text-as-muted">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${value < 0 ? "text-as-negative" : "text-as-text"}`}>
        <span data-tone={attributionTone(value)}>{formatPercent(value)}</span>
      </p>
    </div>
  );
}
