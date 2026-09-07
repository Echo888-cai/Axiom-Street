"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { copilotApi, type CopilotResource } from "@/lib/api/copilot";
import { useLocale, useT } from "@/lib/i18n";
import { PanelSectionTitle } from "./section-title";

// P5-2: model assessment block. Only aggregate facts leave this platform;
// when the provider is disabled the block stays honest and silent.
const POLL_MS = 2_000;
const STALE_MS = 30_000;
const MAX_AWAIT_MS = 120_000;

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

export function InsightBlock({
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
  const [awaiting, setAwaiting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const headAtClick = useRef<string | null>(null);

  const list = useQuery({
    queryKey: ["copilot-insights", strategyId],
    queryFn: () => copilotApi.listInsights(strategyId),
    refetchInterval: awaiting ? pollMs : false,
    staleTime: STALE_MS,
    enabled: providerEnabled,
  });
  const latest = list.data?.[0];

  // A new head row (any status) means the enqueued synthesize finished.
  useEffect(() => {
    if (awaiting && latest && latest.id !== headAtClick.current) {
      setAwaiting(false);
    }
  }, [awaiting, latest]);

  // Safety valve: never spin forever on a lost task.
  useEffect(() => {
    if (!awaiting) return;
    const timer = window.setTimeout(() => setAwaiting(false), MAX_AWAIT_MS);
    return () => window.clearTimeout(timer);
  }, [awaiting]);

  if (!providerEnabled) {
    return (
      <section className="space-y-2">
        <PanelSectionTitle>{t("copilot.insight.title")}</PanelSectionTitle>
        <p className="rounded-xl border border-as-border bg-as-bg px-3 py-2.5 text-[12px] leading-relaxed text-as-muted">
          {t("copilot.insight.disabled")}
        </p>
        <p className="px-0.5 text-[10px] leading-snug text-as-muted">
          {t("copilot.insight.boundary")}
        </p>
      </section>
    );
  }

  async function evaluate() {
    setActionError(null);
    headAtClick.current = latest?.id ?? null;
    setAwaiting(true);
    try {
      await copilotApi.synthesize(resource, id);
    } catch (error) {
      setAwaiting(false);
      setActionError(error instanceof Error ? error.message : String(error));
    }
  }

  const loading = list.isLoading && !latest;
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <PanelSectionTitle>{t("copilot.insight.title")}</PanelSectionTitle>
        {providerName ? (
          <span className="font-mono text-[10px] text-as-muted">{providerName}</span>
        ) : null}
      </div>
      <div className="rounded-xl border border-as-border bg-as-bg px-3 py-2.5">
        {loading ? (
          <div className="space-y-2" aria-busy="true">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        ) : latest?.status === "DONE" ? (
          <div className="space-y-1.5">
            <p className="text-[12.5px] leading-relaxed whitespace-pre-line text-as-text">
              {latest.narrative}
            </p>
            <p className="font-mono text-[10px] tabular-nums text-as-muted">
              {latest.model ? `${latest.model} · ` : ""}
              {latest.created_at ? formatWhen(latest.created_at, locale) : ""}
            </p>
          </div>
        ) : latest?.status === "FAILED" ? (
          <div className="space-y-1">
            <p className="text-[12px] font-medium text-as-negative">
              {t("copilot.insight.failed")}
            </p>
            {latest.error ? (
              <p className="text-[11.5px] leading-relaxed break-words text-as-muted">
                {latest.error}
              </p>
            ) : null}
          </div>
        ) : awaiting ? (
          <p className="text-[12px] text-as-muted">{t("copilot.insight.evaluating")}</p>
        ) : (
          <p className="text-[12px] leading-relaxed text-as-muted">
            {t("copilot.insight.idle")}
          </p>
        )}
        {actionError ? (
          <p className="mt-2 text-[11.5px] leading-relaxed break-words text-as-negative">
            {actionError}
          </p>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] leading-snug text-as-muted">
          {t("copilot.insight.boundary")}
        </p>
        <Button
          size="sm"
          variant={latest?.status === "DONE" ? "secondary" : "primary"}
          disabled={awaiting || list.isLoading}
          onClick={evaluate}
        >
          {awaiting
            ? t("copilot.insight.evaluating")
            : latest?.status === "FAILED" && !actionError
              ? t("copilot.insight.retry")
              : latest?.status === "DONE"
                ? t("copilot.insight.reevaluate")
                : t("copilot.insight.evaluate")}
        </Button>
      </div>
      {list.isError ? (
        <p className="px-0.5 text-[11px] text-as-muted">
          {list.error instanceof Error ? list.error.message : t("copilot.insight.failed")}
        </p>
      ) : null}
    </section>
  );
}
