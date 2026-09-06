"use client";

import {
  ReconcileReports,
  InferredDelistings,
  formatIngestLimits,
  formatReconcileCadence,
  Row,
} from "./data-diagnostics";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type IngestJob } from "@/lib/api";
import { API_URL } from "@/lib/api/http";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { toast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export default function SettingsPage() {
  const qc = useQueryClient();
  const t = useT();
  const [tickers, setTickers] = useState("SPY");
  const [job, setJob] = useState<IngestJob | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const status = useQuery({
    queryKey: ["data-status"],
    queryFn: api.dataStatus,
  });

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  const watchJob = (created: IngestJob, doneOk: string) => {
    setJob(created);
    sourceRef.current?.close();
    const es = new EventSource(api.ingestEventsUrl(created.id));
    sourceRef.current = es;
    es.addEventListener("progress", (ev) => {
      try {
        setJob(JSON.parse((ev as MessageEvent).data) as IngestJob);
      } catch {
        /* ignore malformed frames */
      }
    });
    es.addEventListener("done", (ev) => {
      try {
        const finalJob = JSON.parse((ev as MessageEvent).data) as IngestJob;
        setJob(finalJob);
        qc.invalidateQueries({ queryKey: ["data-status"] });
        if (finalJob.status === "COMPLETED") {
          toast(doneOk, "ok");
        } else {
          toast(finalJob.error?.message || t("common.settings.marketJobFailed"), "err");
        }
      } catch {
        toast(t("common.settings.parseFailedToast"), "err");
      } finally {
        es.close();
        sourceRef.current = null;
      }
    });
    es.onerror = () => {
      /* EventSource retries; terminal state arrives via done */
    };
  };

  const ingest = useMutation({
    mutationFn: () => {
      const symbols = tickers
        .split(/[,;\s]+/)
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);
      return api.ingest({ provider: "auto", start: "2010-01-01", symbols });
    },
    onSuccess: (created) => {
      const names =
        (created.symbols || []).join(", ") || t("common.settings.marketDataWord");
      watchJob(
        created,
        t("common.settings.updatedToastTemplate").split("{names}").join(names),
      );
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const reconcile = useMutation({
    mutationFn: () => api.reconcileMarket(false),
    onSuccess: (body) => {
      watchJob(body.job, t("common.settings.reconcileDoneToast"));
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const running =
    ingest.isPending ||
    reconcile.isPending ||
    (job != null && !["COMPLETED", "FAILED", "CANCELLED"].includes(job.status));
  const cadence = formatReconcileCadence(status.data?.market_reconcile, t);

  const m = status.data?.manifest || {};
  const lean = status.data?.lean_engine;
  const symbolsLabel =
    (status.data?.symbols || []).join(", ") || String(m.symbol || "—");
  const apiKeyExplainParts = t("common.settings.apiKeyExplain").split("{key}");

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title={t("settings.title")}
        description={t("common.settings.description")}
      />

      {status.isError && (
        <Card>
          <EmptyState
            title={t("common.settings.serviceNotConnected")}
            description={status.error.message}
            action={
              <Button variant="secondary" onClick={() => status.refetch()}>
                {t("common.reconnect")}
              </Button>
            }
          />
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 as-stagger">
        <Card>
          <CardHeader title={t("common.settings.runEnvironment")} />
          <dl className="space-y-3 text-sm">
            <Row label="API" value={API_URL} />
            <Row label={t("common.settings.login")} value={t("common.settings.loginLocalUser")} />
            <Row label={t("common.settings.quantEngine")} value={t("common.settings.leanRuntimeValue")} />
          </dl>
        </Card>

        <Card>
          <CardHeader
            title={t("common.settings.marketData")}
            action={
              status.data?.ready ? (
                <Badge tone="green">{t("common.settings.ready")}</Badge>
              ) : (
                <Badge tone="amber">{t("common.settings.missing")}</Badge>
              )
            }
          />
          <dl className="space-y-3 text-sm">
            <Row label={t("data.symbols")} value={symbolsLabel} />
            <Row label={t("data.provider")} value={String(m.source || "—")} />
            <Row
              label={t("common.settings.defaultProvider")}
              value={String(
                (status.data?.providers as { active?: string } | undefined)
                  ?.active || "—",
              )}
            />
            <Row label={t("common.settings.klineCount")} value={String(m.rows ?? "—")} />
            <Row
              label={t("common.settings.range")}
              value={`${m.start ? String(m.start).slice(0, 10) : "—"} → ${m.end ? String(m.end).slice(0, 10) : "—"}`}
            />
            <div className="flex items-center justify-between gap-4">
              <dt className="text-as-muted">SHA256</dt>
              <dd className="flex items-center gap-2 text-xs tabular text-as-muted">
                {m.sha256 ? `${String(m.sha256).slice(0, 12)}…` : "—"}
                {m.sha256 ? (
                  <button
                    type="button"
                    className="cursor-pointer text-as-primary"
                    onClick={() => {
                      navigator.clipboard.writeText(String(m.sha256));
                      toast(t("common.settings.fingerprintCopied"), "ok");
                    }}
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </dd>
            </div>
            <Row
              label={t("data.snapshots")}
              value={String(status.data?.snapshot_key || m.snapshot_key || "—")}
            />
            <Row
              label={t("common.settings.dividendsSplits")}
              value={
                status.data?.corporate_actions_verified === true ||
                m.corporate_actions_verified === true
                  ? t("common.settings.verified")
                  : status.data?.corporate_actions_verified === false ||
                      m.corporate_actions_verified === false
                    ? t("common.settings.notVerified")
                    : "—"
              }
            />
            <Row
              label={t("common.settings.leanData")}
              value={status.data?.lean_ready ? t("common.settings.converted") : t("common.settings.notConverted")}
            />
            <Row label={t("common.settings.fullReconcile")} value={cadence} />
            <Row
              label={t("common.settings.throughput")}
              value={formatIngestLimits(status.data?.ingest_limits, t)}
            />
          </dl>
          {status.data?.quality_report?.issues &&
          status.data.quality_report.issues.length > 0 ? (
            <div className="mt-4 rounded-as border border-as-border bg-as-secondary px-3 py-2 text-xs">
              <div className="mb-1 font-medium text-as-text">{t("common.settings.dataQuality")}</div>
              <ul className="space-y-1 text-as-muted">
                {status.data.quality_report.issues.map((issue) => (
                  <li key={`${issue.rule}-${issue.severity}`}>
                    <span
                      className={
                        issue.severity === "blocking" ? "text-as-negative" : ""
                      }
                    >
                      {issue.severity === "blocking"
                        ? t("common.blocking")
                        : t("common.warning")} · {issue.rule}
                    </span>
                    {" — "}
                    {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : status.data?.ready ? (
            <p className="mt-4 text-xs text-as-muted">
              {t("common.settings.qualityPass")}
            </p>
          ) : null}
          <ReconcileReports
            reports={status.data?.reconcile_reports}
            source={status.data?.reconcile_with}
            ready={Boolean(status.data?.ready)}
          />
          <InferredDelistings
            rows={status.data?.inferred_delistings}
            ready={Boolean(status.data?.ready)}
          />
          <div className="mt-5 space-y-2">
            <label
              className="block text-xs text-as-muted"
              htmlFor="ingest-symbols"
            >
              {t("common.settings.symbolsCsvLabel")}
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                id="ingest-symbols"
                value={tickers}
                onChange={(e) => setTickers(e.target.value)}
                placeholder="SPY, QQQ"
                aria-label={t("common.settings.ingestAria")}
                className="max-w-[220px]"
              />
              <Button
                size="sm"
                onClick={() => ingest.mutate()}
                disabled={running}
              >
                {running ? t("common.settings.fetching") : t("common.settings.fetchMarketData")}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => reconcile.mutate()}
                disabled={running || !status.data?.ready}
                aria-label={t("common.settings.reconcileAria")}
              >
                {t("common.settings.reconcileNow")}
              </Button>
            </div>
            {running && job ? (
              <div className="rounded-as border border-as-border bg-as-secondary/60 px-3 py-2 text-[11px] text-as-muted">
                <div className="flex items-center justify-between gap-3 text-as-text">
                  <span className="font-medium">
                    {job.progress_step || t("common.queued")}
                  </span>
                  <span className="tabular-nums">
                    {job.completed_symbols}/{job.total_symbols || "—"}
                  </span>
                </div>
                {job.current_symbol ? (
                  <p className="mt-1">
                    {t("common.settings.currentSymbol")
                      .split("{sym}")
                      .join(job.current_symbol)}
                  </p>
                ) : (
                  <p className="mt-1">{t("common.settings.workerHint")}</p>
                )}
              </div>
            ) : (
              <p className="text-[11px] text-as-muted">
                {t("common.settings.ingestInfo")}
              </p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title={t("common.settings.leanDocker")} />
          <dl className="space-y-3 text-sm">
            <Row label={t("common.settings.imageLabel")} value={String(lean?.image || "—")} />
            <Row
              label={t("common.settings.probeSource")}
              value={
                lean?.source === "worker"
                  ? t("common.settings.workerSource")
                  : lean?.source === "api"
                    ? t("common.settings.apiLocalSource")
                    : "—"
              }
            />
            <div className="flex items-center justify-between gap-4">
              <dt className="text-as-muted">Docker</dt>
              <dd className="flex items-center gap-2">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    lean?.docker_available
                      ? "bg-as-positive as-live-dot"
                      : "bg-as-negative",
                  )}
                />
                {lean?.docker_available ? (
                  <Badge tone="green">{t("common.settings.available")}</Badge>
                ) : (
                  <Badge tone="red">{t("common.settings.notReady")}</Badge>
                )}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-as-muted">
            {lean?.note || t("common.settings.leanNote")}
          </p>
        </Card>

        <Card>
          <CardHeader title={t("common.settings.apiKeyCard")} />
          <p className="text-sm leading-relaxed text-as-muted">
            {apiKeyExplainParts[0]}
            <code className="text-as-text">POLYGON_API_KEY</code>
            {apiKeyExplainParts[1]}
          </p>
          <ul className="mt-4 space-y-2 text-xs text-as-muted">
            <li>
              <span className="text-as-text">POLYGON_API_KEY</span>
              {t("common.settings.apiKeyDefaultSource")}
            </li>
            <li>
              <span className="text-as-text">ALPACA_API_KEY</span> +{" "}
              <span className="text-as-text">ALPACA_API_SECRET</span>{" — "}
              {t("common.settings.marketAndPaper")}
            </li>
            <li>
              <span className="text-as-text">ALPHA_VANTAGE_API_KEY</span>
            </li>
            <li>
              <span className="text-as-text">TIINGO_API_KEY</span>
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
