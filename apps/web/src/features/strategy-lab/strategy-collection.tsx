"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowUpRight, FlaskConical, Plus, Search } from "lucide-react";
import { Disclosure } from "@/components/ui/disclosure";
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
import { formatRelative, formatTemplate } from "@/lib/utils";
import { useOverview } from "@/features/home/use-overview";
import { ResearchBrief } from "./research-brief";
import { CreateStrategyDialog } from "./create-strategy-dialog";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = [
  "DRAFT",
  "BACKTESTED",
  "VALIDATED",
  "PAPER",
  "APPROVED",
  "LIVE",
  "PAUSED",
  "ARCHIVED",
];

export default function StrategyCollection() {
  const t = useT();
  const overview = useOverview();
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [page, setPage] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const offset = page * PAGE_SIZE;
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["strategies", debounced, statusFilter, page],
    queryFn: () =>
      api.listStrategyPage({
        q: debounced || undefined,
        status: statusFilter === "ALL" ? undefined : statusFilter,
        limit: PAGE_SIZE,
        offset,
      }),
    placeholderData: keepPreviousData,
    refetchInterval: 10000,
  });
  const rows = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasFilter = debounced !== "" || statusFilter !== "ALL";
  const pageCount = Math.max(Math.ceil(total / PAGE_SIZE), 1);

  const clearFilters = () => {
    setSearch("");
    setDebounced("");
    setStatusFilter("ALL");
    setPage(0);
  };

  return (
    <div className="space-y-7 as-enter">
      <PageHeader
        title={t("nav.strategies")}
        description="你的交易想法，集中于此。"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> {t("strategy.newResearch")}
          </Button>
        }
      />
      <ResearchBrief
        overview={overview.data}
        unavailable={overview.isLoading || overview.isError}
      />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          {t("strategy.allStrategies")}{" "}
          <Badge>
            {overview.isLoading || overview.isError
              ? "—"
              : String(overview.data?.strategy_count ?? "—")}
          </Badge>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <select
            aria-label={t("strategy.statusFilterAria")}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
            className="h-9 rounded-lg border border-as-border bg-as-bg px-3 text-sm text-as-text outline-none focus:border-as-primary/40"
          >
            <option value="ALL">{t("strategy.allStatuses")}</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {labelStatus(s)}
              </option>
            ))}
          </select>
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
      </div>
      {isLoading && !data ? (
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
      ) : total === 0 && !hasFilter ? (
        <Card className="flex min-h-[360px] items-center justify-center">
          <EmptyState
            icon={FlaskConical}
            title={t("strategy.collectionEmptyTitle")}
            description={t("strategy.collectionEmptyDesc")}
            action={
              <Button onClick={() => setCreating(true)}>
                <Plus className="h-3.5 w-3.5" />{" "}
                {t("strategy.createFirstResearch")}
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
              <Button variant="ghost" onClick={clearFilters}>
                {t("strategy.clearFilters")}
              </Button>
            }
          />
        </Card>
      ) : (
        <>
          <div className="overflow-hidden rounded-2xl border border-as-border/80 bg-white shadow-as">
            {rows.map((s, index) => (
              <Link
                key={s.id}
                href={`/strategies/${s.id}`}
                className="group flex min-h-[84px] items-center gap-4 border-b border-as-border/60 px-5 py-4 last:border-0 hover:bg-as-secondary/60 focus-visible:outline-offset-[-4px] sm:gap-5 sm:px-6"
              >
                <span className="hidden w-5 text-[11px] tabular text-as-muted sm:block">
                  {String(offset + index + 1).padStart(2, "0")}
                </span>
                <span className="as-icon-well h-10 w-10 rounded-xl">
                  <FlaskConical
                    className="h-[18px] w-[18px]"
                    strokeWidth={1.5}
                    aria-hidden="true"
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-[15px] font-semibold tracking-tight">
                    {s.name}
                  </h2>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-as-muted">
                    <span>{s.benchmark}</span>
                    <span>版本 {s.latest_version?.version ?? 1}</span>
                    <span className="hidden sm:inline">
                      {formatRelative(s.updated_at)}
                    </span>
                  </div>
                </div>
                <Badge tone={s.status === "DRAFT" ? "neutral" : "blue"}>
                  {labelStatus(s.status)}
                </Badge>
                <ArrowUpRight
                  className="hidden h-4 w-4 text-as-muted transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 sm:block"
                  aria-hidden="true"
                />
              </Link>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-as-muted" aria-live="polite">
              {formatTemplate(t("strategy.pageSummary"), {
                from: total === 0 ? 0 : offset + 1,
                to: Math.min(offset + rows.length, total),
                total,
              })}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(p - 1, 0))}
              >
                {t("strategy.prevPage")}
              </Button>
              <Button
                variant="secondary"
                disabled={page >= pageCount - 1}
                onClick={() => setPage((p) => Math.min(p + 1, pageCount - 1))}
              >
                {t("strategy.nextPage")}
              </Button>
            </div>
          </div>
        </>
      )}
      <Disclosure title="第一次使用？从这里开始">
        <ol className="grid gap-4 sm:grid-cols-3">
          <li>
            <span className="mr-2 text-as-primary">01</span>选择模板
            <p className="mt-1 text-xs">新建研究，选一个交易思路。</p>
          </li>
          <li>
            <span className="mr-2 text-as-primary">02</span>设定规则
            <p className="mt-1 text-xs">用表单设置买卖条件，无需编程。</p>
          </li>
          <li>
            <span className="mr-2 text-as-primary">03</span>检验表现
            <p className="mt-1 text-xs">运行历史回测，再验证结果。</p>
          </li>
        </ol>
      </Disclosure>
      <CreateStrategyDialog
        open={creating}
        onClose={() => setCreating(false)}
      />
    </div>
  );
}
