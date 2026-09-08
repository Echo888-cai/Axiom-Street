"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CircleCheck, ClipboardList, Wallet } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, type PaperOrder } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";

const PAPER_READY_STATUSES = new Set(["VALIDATED", "PAPER", "APPROVED"]);

function money(value: number) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function orderId() {
  const suffix = globalThis.crypto?.randomUUID?.() ?? String(Date.now());
  return `paper-ui-${suffix}`;
}

export function PaperDesk() {
  const t = useT();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState("");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [simulationPrice, setSimulationPrice] = useState("");
  const [submitState, setSubmitState] = useState<"idle" | "submitting" | "queued">("idle");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const strategies = useQuery({
    queryKey: ["paper-strategies"],
    queryFn: api.listStrategies,
  });
  const availableStrategies =
    strategies.data?.filter((item) => PAPER_READY_STATUSES.has(item.status)) ?? [];
  const strategyId = selectedId || availableStrategies[0]?.id;
  const positions = useQuery({
    queryKey: ["paper-positions", strategyId],
    queryFn: () => api.getPositions(strategyId!),
    enabled: Boolean(strategyId),
  });
  const orders = useQuery({
    queryKey: ["paper-orders", strategyId],
    queryFn: () => api.listOrders(strategyId!),
    enabled: Boolean(strategyId),
  });
  const reconciliation = useQuery({
    queryKey: ["paper-reconciliation", strategyId],
    queryFn: () => api.getReconciliation(strategyId!),
    enabled: Boolean(strategyId),
  });

  async function submitOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!strategyId) return;
    setSubmitState("submitting");
    setSubmitError(null);
    try {
      await api.createOrder({
        strategy_id: strategyId,
        symbol,
        side,
        quantity: Number(quantity),
        simulation_price: Number(simulationPrice),
        client_order_id: orderId(),
      });
      setSubmitState("queued");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["paper-orders", strategyId] }),
        queryClient.invalidateQueries({ queryKey: ["paper-positions", strategyId] }),
        queryClient.invalidateQueries({ queryKey: ["paper-reconciliation", strategyId] }),
      ]);
    } catch (error) {
      setSubmitState("idle");
      setSubmitError(error instanceof Error ? error.message : t("paper.submitError"));
    }
  }

  if (strategies.isLoading) {
    return <div className="h-80 animate-pulse rounded-as bg-as-secondary" />;
  }

  if (strategies.isError) {
    return <ErrorCard message={t("paper.accountUnavailable")} />;
  }

  if (!availableStrategies.length) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("paper.title")} description={t("paper.description")} />
        <Card>
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-[var(--as-warning)]" />
            <div>
              <h2 className="font-semibold text-as-text">{t("paper.noStrategies")}</h2>
              <p className="mt-1 text-sm text-as-muted">{t("paper.noStrategiesDescription")}</p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  const account = positions.data?.account;
  const positionRows = positions.data?.positions ?? [];
  const orderRows = orders.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("paper.title")}
        description={t("paper.description")}
        action={
          <label className="flex items-center gap-2 text-sm text-as-muted">
            <span>{t("paper.strategy")}</span>
            <select
              aria-label={t("paper.strategy")}
              value={strategyId}
              onChange={(event) => setSelectedId(event.target.value)}
              className="rounded-lg border border-as-border bg-as-bg px-3 py-2 text-sm text-as-text outline-none focus:border-as-primary"
            >
              {availableStrategies.map((strategy) => (
                <option key={strategy.id} value={strategy.id}>
                  {strategy.name}
                </option>
              ))}
            </select>
          </label>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Card>
          <CardHeader title={t("paper.orderTitle")} />
          <form className="space-y-4" onSubmit={submitOrder}>
            <Field label={t("paper.symbol")} htmlFor="paper-symbol">
              <input
                id="paper-symbol"
                aria-label={t("paper.symbol")}
                value={symbol}
                onChange={(event) => setSymbol(event.target.value.toUpperCase())}
                placeholder={t("paper.symbolPlaceholder")}
                required
                className="as-input w-full"
              />
            </Field>
            <div>
              <span className="mb-1.5 block text-xs font-medium text-as-muted">{t("paper.side")}</span>
              <div className="grid grid-cols-2 gap-2">
                {(["BUY", "SELL"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={side === value}
                    onClick={() => setSide(value)}
                    className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${side === value ? "border-as-primary bg-as-primary/10 text-as-primary" : "border-as-border text-as-muted hover:text-as-text"}`}
                  >
                    {value === "BUY" ? t("paper.buy") : t("paper.sell")}
                  </button>
                ))}
              </div>
            </div>
            <Field label={t("paper.quantity")} htmlFor="paper-quantity">
              <input
                id="paper-quantity"
                aria-label={t("paper.quantity")}
                type="number"
                min="0.000001"
                step="any"
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
                required
                className="as-input w-full"
              />
            </Field>
            <Field label={t("paper.simulationPrice")} htmlFor="paper-price">
              <input
                id="paper-price"
                aria-label={t("paper.simulationPrice")}
                type="number"
                min="0.000001"
                step="any"
                value={simulationPrice}
                onChange={(event) => setSimulationPrice(event.target.value)}
                required
                className="as-input w-full"
              />
            </Field>
            {submitError ? <p className="text-sm text-as-negative">{submitError}</p> : null}
            {submitState === "queued" ? (
              <p className="flex items-center gap-2 text-sm text-as-positive">
                <CircleCheck className="h-4 w-4" /> {t("paper.queued")}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={submitState === "submitting"}
              className="as-button-primary w-full rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50"
            >
              {submitState === "submitting" ? t("paper.submitting") : t("paper.submitOrder")}
            </button>
          </form>
        </Card>

        <Card>
          <CardHeader title={t("paper.accountTitle")} />
          {account ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Metric label={t("paper.initialCapital")} value={money(account.initial_capital)} />
              <Metric label={t("paper.cash")} value={money(account.cash)} />
            </div>
          ) : (
            <EmptyBlock icon={<Wallet className="h-5 w-5 text-as-primary" />} title={t("paper.noAccountTitle")} description={t("paper.noAccountDescription")} />
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title={t("paper.positionsTitle")} />
          {positionRows.length ? (
            <div className="space-y-3">
              {positionRows.map((position) => (
                <div key={position.id} className="grid grid-cols-5 gap-2 border-b border-as-border pb-3 text-sm last:border-0 last:pb-0">
                  <span className="font-medium text-as-text">{position.symbol}</span>
                  <span className="text-right text-as-muted">{position.quantity}</span>
                  <span className="text-right text-as-muted">{money(position.average_price)}</span>
                  <span className="text-right text-as-muted">{money(position.mark_price)}</span>
                  <span className={position.realized_pnl < 0 ? "text-right text-as-negative" : "text-right text-as-positive"}>{money(position.realized_pnl)}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyBlock icon={<Wallet className="h-5 w-5 text-as-muted" />} title={t("paper.noPositions")} />
          )}
        </Card>

        <Card>
          <CardHeader title={t("paper.reconciliationTitle")} />
          {reconciliation.data ? (
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-as-muted">{t("paper.reconciliationStatus")}</span>
              <Badge tone={reconciliation.data.status === "MATCHED" ? "green" : "red"}>
                {reconciliation.data.status === "MATCHED" ? t("paper.matched") : t("paper.drift")}
              </Badge>
            </div>
          ) : (
            <EmptyBlock icon={<ClipboardList className="h-5 w-5 text-as-muted" />} title={t("paper.noReconciliation")} />
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title={t("paper.ordersTitle")} />
        {orderRows.length ? (
          <div className="space-y-3">
            {orderRows.map((order) => <OrderRow key={order.id} order={order} t={t} />)}
          </div>
        ) : (
          <EmptyBlock icon={<ClipboardList className="h-5 w-5 text-as-muted" />} title={t("paper.noOrders")} />
        )}
      </Card>
    </div>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="block">
      <span className="mb-1.5 block text-xs font-medium text-as-muted">{label}</span>
      {children}
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-as-border bg-as-secondary/40 p-4"><p className="text-xs text-as-muted">{label}</p><p className="mt-1 font-mono text-lg font-semibold tabular-nums text-as-text">{value}</p></div>;
}

function EmptyBlock({ icon, title, description }: { icon: React.ReactNode; title: string; description?: string }) {
  return <div className="flex items-start gap-3"><div className="mt-0.5">{icon}</div><div><p className="text-sm font-medium text-as-text">{title}</p>{description ? <p className="mt-1 text-sm leading-relaxed text-as-muted">{description}</p> : null}</div></div>;
}

function ErrorCard({ message }: { message: string }) {
  return <Card><p className="text-sm text-as-negative">{message}</p></Card>;
}

function OrderRow({ order, t }: { order: PaperOrder; t: (key: string) => string }) {
  return (
    <div className="grid gap-2 border-b border-as-border pb-3 text-sm last:border-0 last:pb-0 sm:grid-cols-[1.2fr_.7fr_.8fr_1.5fr] sm:items-center">
      <div><p className="font-medium text-as-text">{order.side} {order.symbol}</p><p className="mt-0.5 text-xs text-as-muted">{order.client_order_id}</p></div>
      <span className="text-as-muted">{order.requested_quantity}</span>
      <Badge tone={order.status === "FILLED" ? "green" : order.status === "REJECTED" || order.status === "FAILED" ? "red" : "amber"}>{order.status}</Badge>
      <span className="text-xs text-as-muted">{order.risk_reason || order.error || t("paper.statusColumn")}</span>
    </div>
  );
}
