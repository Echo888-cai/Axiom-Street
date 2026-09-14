"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { useT } from "@/lib/i18n";

const KIND_ORDER = [
  "WALK_FORWARD",
  "DSR",
  "PBO",
  "SENSITIVITY",
  "COST",
  "BOOTSTRAP",
  "REGIME",
  "SPA",
] as const;

export function EvidenceStatus({ strategyId }: { strategyId?: string }) {
  const t = useT();
  const strategiesQuery = useQuery({
    queryKey: ["strategies"],
    queryFn: api.listStrategies,
  });
  // Same effective-selection rule as ValidationLaunch: explicit id wins,
  // otherwise the first strategy. Shared query key keeps it cached.
  const strategies = strategiesQuery.data ?? [];
  const selected = strategies.find((s) => s.id === strategyId) ?? strategies[0];
  const versionId = selected?.latest_version?.id;
  const { data, isLoading, error } = useQuery({
    queryKey: ["validation-evidence", selected?.id, versionId],
    queryFn: () =>
      api.getEvidence({
        strategy_id: selected?.id as string,
        strategy_version_id: versionId as string,
      }),
    enabled: Boolean(selected?.id && versionId),
    refetchInterval: 5000,
  });

  if (!selected) {
    return null;
  }

  const passed = data?.passed ?? {};
  const reasons = data?.reasons ?? {};
  const expired = KIND_ORDER.filter((kind) => !passed[kind]);

  return (
    <Card>
      <CardHeader
        title={t("validation.desk.evidenceTitle")}
        hint={<p className="text-xs text-as-muted">{t("validation.desk.evidenceHint")}</p>}
      />
      {isLoading ? (
        <div className="h-24 animate-pulse rounded-xl bg-as-secondary" />
      ) : error || !data ? (
        <p className="text-sm text-as-muted">{t("validation.errors.apiOfflineHint")}</p>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {expired.length === 0 ? (
              <Badge tone="green">{t("validation.desk.evidenceAllValid")}</Badge>
            ) : (
              <Badge tone="amber">
                {expired.length} {t("validation.desk.evidenceExpired")}
              </Badge>
            )}
            {data.backtest_id ? (
              <span className="text-xs text-as-muted">
                {t("validation.desk.evidenceReference")}{" "}
                <Link
                  href={`/backtests/${data.backtest_id}`}
                  className="text-as-primary hover:underline"
                >
                  {data.backtest_id.slice(0, 8)}…
                </Link>
              </span>
            ) : null}
          </div>
          <ul className="grid gap-2 sm:grid-cols-2">
            {KIND_ORDER.map((kind) => {
              const ok = Boolean(passed[kind]);
              const reason = reasons[kind];
              return (
                <li
                  key={kind}
                  className="flex items-start justify-between gap-3 rounded-xl border border-as-border px-3 py-2"
                >
                  <span className="text-sm font-medium">{kind}</span>
                  <span className="text-right">
                    <Badge tone={ok ? "green" : "red"}>
                      {ok
                        ? t("validation.results.passed")
                        : t("validation.results.failed")}
                    </Badge>
                    {!ok && reason ? (
                      <p className="mt-1 text-xs text-as-muted">
                        {t(`validation.desk.evidenceReasons.${reason}`)}
                      </p>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Card>
  );
}
