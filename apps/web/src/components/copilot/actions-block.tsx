"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { copilotApi, type CopilotResource } from "@/lib/api/copilot";
import { request } from "@/lib/api/http";
import type { CopilotSuggestionCard, ValidationRun } from "@/lib/api/types";
import { useLocale, useT } from "@/lib/i18n";
import { PanelSectionTitle } from "./section-title";

// P5-3: actionable suggestions block. Deterministic cards are always shown
// (executable truth, no model needed); the model may only re-rank them.
const POLL_MS = 2_000;
const STALE_MS = 30_000;
const MAX_AWAIT_MS = 120_000;

// OpenAPI kinds are uppercase; the validation dictionary keys are lowercase.
const KIND_LABEL_KEY: Record<string, string> = {
  DSR: "dsr",
  PBO: "pbo",
  WALK_FORWARD: "walk_forward",
  SENSITIVITY: "sensitivity",
  COST: "cost",
  BOOTSTRAP: "bootstrap",
  REGIME: "regime",
  SPA: "spa",
};

function formatWhen(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(locale, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function isRunCard(card: CopilotSuggestionCard): boolean {
  return card.action === "run_validation";
}

export function ActionsBlock({
  resource,
  id,
  strategyId,
  providerEnabled,
  providerName,
  pollMs = POLL_MS,
}: {
  resource: CopilotResource;
  id: string;
  strategyId: string;
  providerEnabled: boolean;
  providerName: string;
  pollMs?: number;
}) {
  const t = useT();
  const locale = useLocale();
  const qc = useQueryClient();

  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [confirmCard, setConfirmCard] = useState<CopilotSuggestionCard | null>(null);
  const [execError, setExecError] = useState<string | null>(null);

  const cards = useQuery({
    queryKey: ["copilot-suggestions", strategyId],
    queryFn: () => copilotApi.listSuggestions(strategyId),
    staleTime: STALE_MS,
    enabled: Boolean(strategyId),
  });
  const candidates = cards.data?.candidates ?? [];

  const [awaitingRec, setAwaitingRec] = useState(false);
  const recHeadAtClick = useRef<string | null>(null);
  const recommendation = useQuery({
    queryKey: ["copilot-suggestion-rec", strategyId],
    queryFn: () => copilotApi.getRecommendation(strategyId),
    refetchInterval: awaitingRec ? pollMs : false,
    staleTime: STALE_MS,
    enabled: providerEnabled && Boolean(strategyId),
  });
  const latestRec = recommendation.data;

  // A new recommendation row (any status) means the enqueued sort finished.
  useEffect(() => {
    if (awaitingRec && latestRec && latestRec.id !== recHeadAtClick.current) {
      setAwaitingRec(false);
    }
  }, [awaitingRec, latestRec]);

  useEffect(() => {
    if (!awaitingRec) return;
    const timer = window.setTimeout(() => setAwaitingRec(false), MAX_AWAIT_MS);
    return () => window.clearTimeout(timer);
  }, [awaitingRec]);

  function kindLabel(kind?: string | null): string {
    if (!kind) return "";
    const key = KIND_LABEL_KEY[kind] ?? kind;
    return t(`validation.kinds.${key}`);
  }

  function reasonText(card: CopilotSuggestionCard): string {
    return t(`copilot.suggestions.reason.${card.reason_code}`);
  }

  async function adopt(card: CopilotSuggestionCard) {
    setPendingKey(card.key);
    setExecError(null);
    try {
      await request<ValidationRun>("/api/v1/validation", {
        method: "POST",
        body: JSON.stringify({
          kind: card.validation_kind,
          strategy_version_id: card.strategy_version_id,
          backtest_id: card.template_backtest_id ?? undefined,
          params: card.params ?? {},
        }),
      });
      toast(t("copilot.suggestions.queued"), "ok");
      qc.invalidateQueries({ queryKey: ["copilot-suggestions", strategyId] });
      qc.invalidateQueries({ queryKey: ["copilot-context", resource, id] });
      qc.invalidateQueries({ queryKey: ["validation-runs"] });
    } catch (error) {
      setExecError(error instanceof Error ? error.message : String(error));
      toast(error instanceof Error ? error.message : String(error), "err");
    } finally {
      setPendingKey(null);
    }
  }

  const loading = cards.isLoading && candidates.length === 0;

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <PanelSectionTitle>{t("copilot.suggestions.title")}</PanelSectionTitle>
        {cards.data ? (
          <span className="font-mono text-[10px] tabular-nums text-as-muted">
            {candidates.length}
          </span>
        ) : null}
      </div>

      <div className="rounded-xl border border-as-border bg-as-bg px-3 py-2.5">
        {loading ? (
          <div className="space-y-2" aria-busy="true">
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : candidates.length === 0 ? (
          <p className="text-[12px] leading-relaxed text-as-muted">
            {t("copilot.suggestions.empty")}
          </p>
        ) : (
          <ul className="space-y-2">
            {candidates.map((card) => {
              if (isRunCard(card)) {
                return (
                  <li key={card.key} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-medium text-as-text">
                          {kindLabel(card.validation_kind)}
                        </p>
                        <p className="text-[11.5px] leading-snug text-as-muted">
                          {reasonText(card)}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant={pendingKey === card.key ? "secondary" : "primary"}
                        disabled={pendingKey === card.key}
                        onClick={() => setConfirmCard(card)}
                      >
                        {pendingKey === card.key
                          ? t("copilot.suggestions.submitting")
                          : t("copilot.suggestions.adopt")}
                      </Button>
                    </div>
                  </li>
                );
              }
              return (
                <li
                  key={card.key}
                  className="rounded-lg border border-as-border bg-as-bg px-2.5 py-2"
                >
                  <p className="text-[12px] leading-relaxed text-as-muted">
                    {reasonText(card)}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {cards.isError ? (
        <p className="px-0.5 text-[11px] text-as-muted">
          {cards.error instanceof Error
            ? cards.error.message
            : t("copilot.suggestions.failed")}
        </p>
      ) : null}

      {providerEnabled ? (
        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11.5px] font-medium text-as-text">
              {t("copilot.suggestions.model.title")}
            </p>
            {providerName ? (
              <span className="font-mono text-[10px] text-as-muted">{providerName}</span>
            ) : null}
          </div>
          <div className="rounded-xl border border-as-border bg-as-bg px-3 py-2.5">
            {recommendation.isLoading && !latestRec ? (
              <Skeleton className="h-10 w-full" />
            ) : latestRec?.status === "DONE" ? (
              <div className="space-y-1">
                <p className="text-[12px] font-medium text-as-text">
                  {t("copilot.suggestions.model.pick")}
                </p>
                <p className="text-[12px] leading-relaxed text-as-text">{latestRec.reason}</p>
                <p className="font-mono text-[10px] tabular-nums text-as-muted">
                  {latestRec.created_at ? formatWhen(latestRec.created_at, locale) : ""}
                </p>
              </div>
            ) : latestRec?.status === "FAILED" ? (
              <div className="space-y-1">
                <p className="text-[12px] font-medium text-as-negative">
                  {t("copilot.suggestions.model.failed")}
                </p>
                {latestRec.error ? (
                  <p className="text-[11.5px] leading-relaxed break-words text-as-muted">
                    {latestRec.error}
                  </p>
                ) : null}
              </div>
            ) : awaitingRec ? (
              <p className="text-[12px] text-as-muted">
                {t("copilot.suggestions.model.ordering")}
              </p>
            ) : (
              <p className="text-[12px] leading-relaxed text-as-muted">
                {t("copilot.suggestions.model.idle")}
              </p>
            )}
          </div>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] leading-snug text-as-muted">
              {t("copilot.suggestions.model.boundary")}
            </p>
            <Button
              size="sm"
              variant="secondary"
              disabled={awaitingRec || recommendation.isLoading || candidates.length === 0}
              onClick={async () => {
                recHeadAtClick.current = latestRec?.id ?? null;
                setAwaitingRec(true);
                try {
                  await copilotApi.suggest(resource, id);
                } catch (error) {
                  setAwaitingRec(false);
                  toast(error instanceof Error ? error.message : String(error), "err");
                }
              }}
            >
              {awaitingRec
                ? t("copilot.suggestions.model.ordering")
                : t("copilot.suggestions.model.order")}
            </Button>
          </div>
        </div>
      ) : null}

      {execError ? (
        <p className="px-0.5 text-[11px] leading-snug text-as-negative">
          {t("copilot.suggestions.failed")}: {execError}
        </p>
      ) : null}

      <ConfirmDialog
        open={confirmCard !== null}
        title={t("copilot.suggestions.confirm.title")}
        description={
          confirmCard
            ? `${kindLabel(confirmCard.validation_kind)} · ${t(
                "copilot.suggestions.confirm.note",
              )} · ${t("copilot.suggestions.confirm.version")} v${
                confirmCard.target_version ?? ""
              }`
            : undefined
        }
        confirmLabel={t("copilot.suggestions.confirm.submit")}
        onConfirm={() => {
          const card = confirmCard;
          setConfirmCard(null);
          if (card && isRunCard(card)) {
            void adopt(card);
          }
        }}
        onClose={() => setConfirmCard(null)}
      />
    </section>
  );
}
