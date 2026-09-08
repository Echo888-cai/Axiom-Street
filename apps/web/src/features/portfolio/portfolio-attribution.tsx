"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BarChart3, Layers3 } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
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

function messageFrom(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function PortfolioAttribution() {
  const t = useT();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState("");
  const portfolios = useQuery({ queryKey: ["portfolios"], queryFn: api.listPortfolios });
  const strategies = useQuery({ queryKey: ["portfolio-strategies"], queryFn: api.listStrategies });
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

  if (portfolios.isLoading) return <div className="h-80 animate-pulse rounded-as bg-as-secondary" />;
  if (portfolios.isError) {
    return <Card><div className="flex items-start gap-3 text-as-negative"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" /><div><h2 className="font-semibold">{t("portfolio.loadErrorTitle")}</h2><p className="mt-1 text-sm text-as-muted">{t("portfolio.loadErrorDescription")}</p></div></div></Card>;
  }

  if (!portfolios.data?.length) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("portfolio.title")} description={t("portfolio.description")} />
        <Card><div className="flex items-start gap-3"><Layers3 className="mt-0.5 h-5 w-5 text-as-primary" /><div><h2 className="font-semibold text-as-text">{t("portfolio.emptyTitle")}</h2><p className="mt-1 text-sm text-as-muted">{t("portfolio.emptyDescription")}</p></div></div></Card>
        <CreatePortfolioCard t={t} queryClient={queryClient} />
      </div>
    );
  }

  const portfolio = portfolios.data.find((item) => item.id === portfolioId) ?? portfolios.data[0];
  const latest = latestAttribution(attribution.data);
  const strategyRows = strategies.data ?? [];
  const strategyNames = new Map(strategyRows.map((strategy) => [strategy.id, strategy.name]));

  return (
    <div className="space-y-6">
      <PageHeader title={t("portfolio.title")} description={t("portfolio.description")} action={<label className="flex items-center gap-2 text-sm text-as-muted"><span className="sr-only">{t("portfolio.selectLabel")}</span><select aria-label={t("portfolio.selectLabel")} value={portfolio.id} onChange={(event) => setSelectedId(event.target.value)} className="rounded-lg border border-as-border bg-as-bg px-3 py-2 text-sm text-as-text outline-none focus:border-as-primary">{portfolios.data.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>} />
      <CreatePortfolioCard t={t} queryClient={queryClient} compact />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title={t("portfolio.allocationTitle")} hint={<Badge tone="blue">{portfolio.base_currency}</Badge>} />
          {allocations.isLoading ? <div className="h-24 animate-pulse rounded-lg bg-as-secondary" /> : allocations.data?.length ? <div className="space-y-3">{allocations.data.map((item) => <div key={item.id} className="flex items-center justify-between gap-3 border-b border-as-border pb-3 last:border-0 last:pb-0"><div className="min-w-0"><p className="truncate text-sm font-medium text-as-text">{strategyNames.get(item.strategy_id) ?? `${t("portfolio.strategyPrefix")} ${item.strategy_id.slice(0, 8)}`}</p><p className="mt-0.5 text-xs text-as-muted">{item.effective_from}</p></div><span className="text-sm font-semibold text-as-text">{formatWeight(item.weight)}</span></div>)}</div> : <p className="text-sm text-as-muted">{t("portfolio.noAllocations")}</p>}
          <AllocationForm portfolioId={portfolio.id} strategies={strategyRows} allocations={allocations.data ?? []} t={t} queryClient={queryClient} />
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title={t("portfolio.attributionTitle")} hint={latest ? <span className="text-xs text-as-muted">{t("portfolio.asOf")} {latest.as_of}</span> : undefined} />
          {attribution.isLoading ? <div className="h-24 animate-pulse rounded-lg bg-as-secondary" /> : latest ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label={t("portfolio.portfolioReturn")} value={latest.portfolio_return} /><Metric label={t("portfolio.benchmarkReturn")} value={latest.benchmark_return} /><Metric label={t("portfolio.activeReturn")} value={latest.active_return} /><Metric label={t("portfolio.allocationEffect")} value={latest.allocation_effect} /><Metric label={t("portfolio.selectionEffect")} value={latest.selection_effect} /><Metric label={t("portfolio.interactionEffect")} value={latest.interaction_effect} /></div> : <p className="text-sm text-as-muted">{t("portfolio.noAttribution")}</p>}
          <AttributionForm portfolioId={portfolio.id} allocations={allocations.data ?? []} strategyNames={strategyNames} t={t} queryClient={queryClient} />
        </Card>
      </div>

      <Card><CardHeader title={t("portfolio.factorTitle")} hint={<Badge tone="amber">{t("portfolio.notAvailableBadge")}</Badge>} /><div className="flex items-start gap-3"><BarChart3 className="mt-0.5 h-5 w-5 shrink-0 text-[var(--as-warning)]" /><p className="text-sm leading-relaxed text-as-muted">{t("portfolio.factorDescription")}</p></div></Card>
    </div>
  );
}

function CreatePortfolioCard({ t, queryClient, compact = false }: { t: (key: string) => string; queryClient: ReturnType<typeof useQueryClient>; compact?: boolean }) {
  const [name, setName] = useState("");
  const [capital, setCapital] = useState("100000");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null); setCreated(false);
    try { await api.createPortfolio({ name, base_currency: "USD", initial_capital: Number(capital) }); setCreated(true); await queryClient.invalidateQueries({ queryKey: ["portfolios"] }); }
    catch (reason) { setError(messageFrom(reason, t("portfolio.createError"))); }
  }

  return <Card><CardHeader title={t("portfolio.createTitle")} hint={compact ? <span className="text-xs text-as-muted">{t("portfolio.createHint")}</span> : undefined} /><form className="grid gap-3 md:grid-cols-[1.4fr_.8fr_auto] md:items-end" onSubmit={submit}><InputField label={t("portfolio.portfolioName")} htmlFor="portfolio-name"><input id="portfolio-name" aria-label={t("portfolio.portfolioName")} value={name} onChange={(event) => setName(event.target.value)} required className="as-input w-full" /></InputField><InputField label={t("portfolio.initialCapital")} htmlFor="portfolio-capital"><input id="portfolio-capital" aria-label={t("portfolio.initialCapital")} type="number" min="0.01" step="any" value={capital} onChange={(event) => setCapital(event.target.value)} required className="as-input w-full" /></InputField><button type="submit" className="as-button-primary rounded-lg px-4 py-2.5 text-sm font-medium">{t("portfolio.createButton")}</button></form>{created ? <p className="mt-3 text-sm text-as-positive">{t("portfolio.created")}</p> : null}{error ? <p className="mt-3 text-sm text-as-negative">{error}</p> : null}</Card>;
}

function AllocationForm({ portfolioId, strategies, allocations, t, queryClient }: { portfolioId: string; strategies: Array<{ id: string; name: string }>; allocations: Array<{ weight: number }>; t: (key: string) => string; queryClient: ReturnType<typeof useQueryClient> }) {
  const [strategyId, setStrategyId] = useState(""); const [weight, setWeight] = useState(""); const [effectiveFrom, setEffectiveFrom] = useState(""); const [error, setError] = useState<string | null>(null);
  const total = allocations.reduce((sum, item) => sum + item.weight, 0);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setError(null); try { await api.createAllocation(portfolioId, { strategy_id: strategyId, weight: Number(weight), effective_from: effectiveFrom }); await queryClient.invalidateQueries({ queryKey: ["portfolio-allocations", portfolioId] }); } catch (reason) { setError(messageFrom(reason, t("portfolio.allocationError"))); } }
  return <form className="mt-5 space-y-3 border-t border-as-border pt-5" onSubmit={submit}><p className="text-xs font-medium text-as-muted">{t("portfolio.addAllocationTitle")}</p><select aria-label={t("portfolio.configureStrategy")} value={strategyId} onChange={(event) => setStrategyId(event.target.value)} required className="as-input w-full"><option value="">{t("portfolio.chooseStrategy")}</option>{strategies.map((strategy) => <option key={strategy.id} value={strategy.id}>{strategy.name}</option>)}</select><div className="grid gap-3 sm:grid-cols-2"><input aria-label={t("portfolio.configureWeight")} type="number" min="0" max="1" step="any" value={weight} onChange={(event) => setWeight(event.target.value)} placeholder={t("portfolio.weightPlaceholder")} required className="as-input w-full" /><input aria-label={t("portfolio.effectiveFrom")} type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} required className="as-input w-full" /></div><p className="text-xs text-as-muted">{t("portfolio.weightTotal")} {formatWeight(total)} · {t("portfolio.weightHint")}</p>{error ? <p className="text-sm text-as-negative">{error}</p> : null}<button type="submit" className="as-button-secondary w-full rounded-lg px-3 py-2 text-sm font-medium">{t("portfolio.addAllocation")}</button></form>;
}

function AttributionForm({ portfolioId, allocations, strategyNames, t, queryClient }: { portfolioId: string; allocations: Array<{ strategy_id: string }>; strategyNames: Map<string, string>; t: (key: string) => string; queryClient: ReturnType<typeof useQueryClient> }) {
  const [asOf, setAsOf] = useState(""); const [returns, setReturns] = useState<Record<string, { strategy: string; benchmark: string }>>({}); const [error, setError] = useState<string | null>(null); const [created, setCreated] = useState(false);
  function updateReturn(strategyId: string, field: "strategy" | "benchmark", value: string) { setReturns((current) => ({ ...current, [strategyId]: { strategy: current[strategyId]?.strategy ?? "", benchmark: current[strategyId]?.benchmark ?? "", [field]: value } })); }
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setError(null); setCreated(false); try { await api.createAttribution(portfolioId, { as_of: asOf, returns: allocations.map((item) => ({ strategy_id: item.strategy_id, strategy_return: Number(returns[item.strategy_id]?.strategy), benchmark_return: Number(returns[item.strategy_id]?.benchmark) })) }); setCreated(true); await queryClient.invalidateQueries({ queryKey: ["portfolio-attribution", portfolioId] }); } catch (reason) { setError(messageFrom(reason, t("portfolio.attributionError"))); } }
  if (!allocations.length) return null;
  return <form className="mt-6 space-y-3 border-t border-as-border pt-5" onSubmit={submit}><p className="text-xs font-medium text-as-muted">{t("portfolio.submitAttributionTitle")}</p><input aria-label={t("portfolio.attributionDate")} type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} required className="as-input w-full" />{allocations.map((item) => { const suffix = strategyNames.get(item.strategy_id) ?? item.strategy_id.slice(0, 8); return <div key={item.strategy_id} className="grid gap-2 sm:grid-cols-3 sm:items-end"><span className="text-sm text-as-text">{suffix}</span><input aria-label={`${t("portfolio.strategyReturn")} ${suffix}`} type="number" step="any" placeholder={t("portfolio.strategyReturn")} onChange={(event) => updateReturn(item.strategy_id, "strategy", event.target.value)} required className="as-input w-full" /><input aria-label={`${t("portfolio.benchmarkReturn")} ${suffix}`} type="number" step="any" placeholder={t("portfolio.benchmarkReturn")} onChange={(event) => updateReturn(item.strategy_id, "benchmark", event.target.value)} required className="as-input w-full" /></div>; })}{created ? <p className="text-sm text-as-positive">{t("portfolio.attributionCreated")}</p> : null}{error ? <p className="text-sm text-as-negative">{error}</p> : null}<button type="submit" className="as-button-secondary w-full rounded-lg px-3 py-2 text-sm font-medium">{t("portfolio.submitAttribution")}</button></form>;
}

function InputField({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) { return <label htmlFor={htmlFor} className="block"><span className="mb-1.5 block text-xs font-medium text-as-muted">{label}</span>{children}</label>; }

function Metric({ label, value }: { label: string; value: number }) { return <div className="rounded-lg border border-as-border bg-as-secondary/40 p-3"><p className="text-xs text-as-muted">{label}</p><p className={`mt-1 text-lg font-semibold ${value < 0 ? "text-as-negative" : "text-as-text"}`}><span data-tone={attributionTone(value)}>{formatPercent(value)}</span></p></div>; }
