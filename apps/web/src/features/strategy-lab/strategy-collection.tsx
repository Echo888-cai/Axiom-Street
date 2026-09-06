"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  FlaskConical,
  Plus,
  Search,
  Layers,
  Code2,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n";
import { labelStatus } from "@/lib/labels";
import { formatRelative } from "@/lib/utils";
import { CreateStrategyDialog } from "./create-strategy-dialog";

export default function StrategyCollection() {
  const t = useT();
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["strategies"],
    queryFn: api.listStrategies,
  });
  const rows = useMemo(
    () =>
      (data || []).filter((s) =>
        `${s.name} ${s.description || ""} ${s.benchmark}`
          .toLowerCase()
          .includes(search.trim().toLowerCase()),
      ),
    [data, search],
  );
  return (
    <div className="space-y-7 as-enter">
      <PageHeader
        title={t("nav.strategies")}
        description={t("strategy.collectionDescription")}
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> {t("strategy.newResearch")}
          </Button>
        }
      />
      <div className="grid gap-4 md:grid-cols-3">
        {[
          {
            n: "01",
            title: t("strategy.stepWriteTitle"),
            text: t("strategy.stepWriteText"),
            icon: FlaskConical,
          },
          {
            n: "02",
            title: t("strategy.stepBuildTitle"),
            text: t("strategy.stepBuildText"),
            icon: Code2,
          },
          {
            n: "03",
            title: t("strategy.stepIterateTitle"),
            text: t("strategy.stepIterateText"),
            icon: Layers,
          },
        ].map((step) => (
          <div
            key={step.n}
            className="flex items-center gap-3 rounded-2xl border border-white bg-white/55 p-5"
          >
            <span className="as-icon-well h-10 w-10 rounded-xl">
              <step.icon className="h-4 w-4" strokeWidth={1.5} />
            </span>
            <div className="flex-1">
              <p className="text-xs font-medium">{step.title}</p>
              <p className="mt-1 text-[11px] text-as-muted">{step.text}</p>
            </div>
            <span className="text-[10px] tabular text-as-muted/70">
              {step.n}
            </span>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          {t("strategy.allStrategies")}{" "}
          <Badge>{isLoading || error ? "—" : String(data?.length || 0)}</Badge>
        </div>
        <div className="relative w-full sm:w-64">
          <Search className="pointer-events-none absolute left-3 top-3.5 h-3.5 w-3.5 text-as-muted" />
          <Input
            aria-label={t("strategy.searchAria")}
            placeholder={t("strategy.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9"
          />
        </div>
      </div>
      {isLoading ? (
        <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-52" />
          ))}
        </div>
      ) : error ? (
        <Card>
          <EmptyState
            icon={FlaskConical}
            title={t("strategy.collectionLoadErrorTitle")}
            description={t("strategy.collectionLoadErrorDesc")}
            action={
              <Button variant="secondary" onClick={() => refetch()}>
                {t("strategy.reconnect")}
              </Button>
            }
          />
        </Card>
      ) : !data?.length ? (
        <Card className="flex min-h-[360px] items-center justify-center">
          <EmptyState
            icon={FlaskConical}
            title={t("strategy.collectionEmptyTitle")}
            description={t("strategy.collectionEmptyDesc")}
            action={
              <Button onClick={() => setCreating(true)}>
                <Plus className="h-3.5 w-3.5" /> {t("strategy.createFirstResearch")}
              </Button>
            }
          />
        </Card>
      ) : !rows.length ? (
        <Card>
          <EmptyState
            icon={Search}
            title={t("strategy.noMatchTitle")}
            description={t("strategy.noMatchDesc")}
            action={
              <Button variant="ghost" onClick={() => setSearch("")}>
                {t("strategy.clearSearch")}
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3 as-stagger">
          {rows.map((s) => (
            <Link key={s.id} href={`/strategies/${s.id}`} className="group">
              <Card hover className="flex h-full min-h-[230px] flex-col">
                <div className="mb-6 flex items-center justify-between">
                  <span className="as-icon-well h-11 w-11 rounded-2xl">
                    <FlaskConical
                      className="h-[18px] w-[18px]"
                      strokeWidth={1.5}
                    />
                  </span>
                  <Badge>{labelStatus(s.status)}</Badge>
                </div>
                <h2 className="text-base font-semibold tracking-tight">
                  {s.name}
                </h2>
                <p className="mb-6 mt-2 line-clamp-2 text-xs leading-6 text-as-muted">
                  {s.description || t("strategy.cardMissingDescription")}
                </p>
                <div className="mt-auto flex items-center gap-2 border-t border-as-border pt-4 text-[10px] text-as-muted">
                  <Badge tone="blue">{s.benchmark}</Badge>
                  <span>v{s.latest_version?.version ?? 1}</span>
                  <span className="ml-auto">
                    {formatRelative(s.updated_at)}
                  </span>
                  <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
      <CreateStrategyDialog
        open={creating}
        onClose={() => setCreating(false)}
      />
    </div>
  );
}
