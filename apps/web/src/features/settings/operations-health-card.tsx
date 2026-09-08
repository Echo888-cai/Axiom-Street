"use client";

import { Activity, AlertTriangle, RefreshCw, ShieldCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, type HealthCheck, type HealthStatus } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";

function statusTone(status: HealthStatus["status"]): "green" | "amber" | "red" {
  return status === "ok" ? "green" : status === "down" ? "red" : "amber";
}

function checkTone(check: HealthCheck | undefined): "green" | "amber" | "red" {
  return check?.ok ? "green" : "red";
}

export function OperationsHealthCard() {
  const t = useT();
  const health = useQuery({
    queryKey: ["operations-health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });

  if (health.isLoading) {
    return <div className="h-48 animate-pulse rounded-as bg-as-secondary" />;
  }
  if (health.isError) {
    return (
      <Card>
        <CardHeader title={t("common.settings.operationsHealthTitle")} />
        <div className="flex items-start gap-3 text-sm text-as-negative">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">{t("common.settings.operationsHealthUnavailable")}</p>
            <p className="mt-1 text-xs text-as-muted">{health.error.message}</p>
          </div>
        </div>
      </Card>
    );
  }

  const data = health.data;
  if (!data) return null;
  const worker = data.checks.worker;
  const security = data.checks.security;
  const workerAge = typeof worker?.age_seconds === "number"
    ? `${Math.round(worker.age_seconds)} ${t("common.settings.operationsSecondsAgo")}`
    : t("common.settings.operationsUnavailable");
  const securitySummary = security?.ok
    ? t("common.settings.operationsSandboxReady")
    : security?.note || t("common.settings.operationsSandboxUnavailable");

  return (
    <Card>
      <CardHeader
        title={t("common.settings.operationsHealthTitle")}
        action={
          <div className="flex items-center gap-2">
            <Badge tone={statusTone(data.status)}>
              {t(`common.settings.operationsStatus.${data.status}`)}
            </Badge>
            <Button
              size="sm"
              variant="secondary"
              aria-label={t("common.settings.operationsRefresh")}
              onClick={() => void health.refetch()}
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        }
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <HealthTile label="API" check={data.checks.postgres} value={data.service} />
        <HealthTile label={t("common.settings.operationsWorker")} check={worker} value={workerAge} />
        <HealthTile
          label={t("common.settings.operationsDocker")}
          check={data.checks.docker}
          value={data.checks.docker?.image || t("common.settings.operationsUnavailable")}
        />
        <HealthTile
          label={t("common.settings.operationsSandbox")}
          check={security}
          value={securitySummary}
          icon={<ShieldCheck className="h-4 w-4" />}
        />
      </div>
      {worker?.note ? <p className="mt-4 text-xs text-as-muted">{worker.note}</p> : null}
      <p className="mt-3 flex items-center gap-1.5 text-[11px] text-as-muted">
        <Activity className="h-3.5 w-3.5" />
        {t("common.settings.operationsMetricsHint")}
      </p>
    </Card>
  );
}

function HealthTile({
  label,
  check,
  value,
  icon,
}: {
  label: string;
  check: HealthCheck | undefined;
  value: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-as-border bg-as-secondary/40 p-3">
      <div className="flex items-center gap-2 text-xs text-as-muted">
        <span className={`h-1.5 w-1.5 rounded-full ${check?.ok ? "bg-as-positive" : "bg-as-negative"}`} />
        {icon}
        <span>{label}</span>
        <Badge className="ml-auto" tone={checkTone(check)}>{check?.ok ? "OK" : "—"}</Badge>
      </div>
      <p className="mt-2 truncate text-sm text-as-text" title={value}>{value}</p>
    </div>
  );
}
