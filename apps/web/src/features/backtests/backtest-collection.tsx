"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  LineChart,
  Plus,
  Search,
  CheckCheck,
  Timer,
  Archive,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { BACKTEST_TONE, labelStatus } from "@/lib/labels";
import { formatNumber, formatPct, cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

const ACTIVE = ["QUEUED", "STARTING", "RUNNING"];

export default function BacktestCollection() {
  const t = useT();
  const [filter, setFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["backtests"],
    queryFn: () => api.listBacktests(),
    refetchInterval: 10_000,
  });
  const rows = useMemo(
    () =>
      (data || []).filter(
        (b) =>
          (filter === "ALL" ||
            (filter === "RUNNING"
              ? ACTIVE.includes(b.status)
              : b.status === filter)) &&
          `${b.strategy_name || ""} ${b.benchmark}`
            .toLowerCase()
            .includes(search.trim().toLowerCase()),
      ),
    [data, filter, search],
  );
  const filterItems = [
    { id: "ALL", label: t("backtest.collection.filterAll") },
    { id: "COMPLETED", label: t("backtest.status.completed") },
    { id: "RUNNING", label: t("backtest.collection.filterRunning") },
    { id: "FAILED", label: t("backtest.status.failed") },
  ];
  const stats = [
    { label: t("backtest.collection.statRecords"), count: data?.length, icon: Archive },
    {
      label: t("backtest.collection.statCompleted"),
      count: data?.filter((b) => b.status === "COMPLETED").length,
      icon: CheckCheck,
    },
    {
      label: t("backtest.collection.statRunning"),
      count: data?.filter((b) => ACTIVE.includes(b.status)).length,
      icon: Timer,
    },
  ];
  const headers = [
    t("backtest.collection.colResearch"),
    t("backtest.collection.colRange"),
    t("backtest.collection.colCumReturn"),
    t("backtest.metrics.sharpe"),
    t("backtest.metrics.maxDrawdown"),
    t("backtest.collection.colStatus"),
    "",
  ];
  return (
    <div className="space-y-7 as-enter">
      <PageHeader
        title={t("backtest.collection.title")}
        description={t("backtest.collection.subtitle")}
        action={
          <Link
            href="/strategies"
            className="as-button-primary inline-flex min-h-11 items-center gap-2 rounded-xl px-4 text-xs text-white"
          >
            <Plus className="h-4 w-4" /> {t("backtest.collection.runNew")}
          </Link>
        }
      />
      <div className="grid grid-cols-3 gap-3 sm:gap-5">
        {stats.map((stat) => (
          <Card
            key={stat.label}
            className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"
          >
            <div>
              <p className="text-[11px] text-as-muted">{stat.label}</p>
              <p className="mt-3 text-[28px] font-medium tabular tracking-tight">
                {isLoading || error ? "—" : (stat.count ?? 0)}
              </p>
            </div>
            <span className="as-icon-well hidden h-11 w-11 rounded-2xl sm:flex">
              <stat.icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
            </span>
          </Card>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Tabs value={filter} onChange={setFilter} items={filterItems} />
        <div className="relative w-full sm:w-60">
          <Search className="pointer-events-none absolute left-3 top-3.5 h-3.5 w-3.5 text-as-muted" />
          <Input
            aria-label={t("backtest.collection.searchLabel")}
            placeholder={t("backtest.collection.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9"
          />
        </div>
      </div>
      <Card className="overflow-hidden p-0 sm:p-0">
        {isLoading ? (
          <div className="space-y-3 p-6">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : error ? (
          <EmptyState
            icon={LineChart}
            title={t("backtest.collection.errorTitle")}
            description={t("backtest.collection.errorDesc")}
            action={
              <Button variant="secondary" onClick={() => refetch()}>
                {t("backtest.collection.reconnect")}
              </Button>
            }
          />
        ) : !data?.length ? (
          <div className="py-10">
            <EmptyState
              icon={LineChart}
              title={t("backtest.collection.emptyTitle")}
              description={t("backtest.collection.emptyDesc")}
              action={
                <Link
                  href="/strategies"
                  className="as-button-secondary inline-flex min-h-10 items-center gap-2 rounded-xl border border-as-border px-4 text-xs"
                >
                  {t("backtest.collection.openLab")} <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              }
            />
          </div>
        ) : !rows.length ? (
          <EmptyState
            icon={Search}
            title={t("backtest.collection.noMatch")}
            action={
              <Button
                variant="ghost"
                onClick={() => {
                  setFilter("ALL");
                  setSearch("");
                }}
              >
                {t("backtest.collection.resetFilters")}
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[660px] text-left">
              <thead className="border-b border-as-border bg-as-secondary/45 text-[10px] font-normal text-as-muted">
                <tr>
                  {headers.map((label, i) => (
                    <th
                      key={i}
                      scope="col"
                      className="whitespace-nowrap px-5 py-4 font-medium"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-as-border">
                {rows.map((bt) => (
                  <tr
                    key={bt.id}
                    className="group text-xs transition-colors hover:bg-as-secondary/45"
                  >
                    <td className="px-5 py-5">
                      <Link
                        href={`/backtests/${bt.id}`}
                        className="block font-medium hover:text-as-primary"
                      >
                        {bt.strategy_name || t("backtest.collection.unnamed")}
                      </Link>
                      <span className="mt-1.5 block text-[10px] text-as-muted">
                        {bt.benchmark}{" "}
                        {bt.version_number ? `· v${bt.version_number}` : ""}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-5 text-[11px] tabular text-as-muted">
                      {bt.start_date}
                      <br />
                      <span className="mt-1 inline-block">{bt.end_date}</span>
                    </td>
                    <td
                      className={cn(
                        "px-5 tabular",
                        bt.status === "COMPLETED" && bt.total_return != null
                          ? bt.total_return >= 0
                            ? "text-as-positive"
                            : "text-as-negative"
                          : "text-as-muted",
                      )}
                    >
                      {bt.status === "COMPLETED"
                        ? formatPct(bt.total_return)
                        : "—"}
                    </td>
                    <td className="px-5 tabular">
                      {bt.status === "COMPLETED"
                        ? formatNumber(bt.sharpe)
                        : "—"}
                    </td>
                    <td className="px-5 tabular text-as-muted">
                      {bt.status === "COMPLETED"
                        ? formatPct(bt.max_drawdown)
                        : "—"}
                    </td>
                    <td className="px-5">
                      <Badge tone={BACKTEST_TONE[bt.status] || "neutral"}>
                        {labelStatus(bt.status)}
                      </Badge>
                    </td>
                    <td className="pr-5">
                      <Link
                        href={`/backtests/${bt.id}`}
                        aria-label={t("backtest.collection.viewAria").replace(
                          "{name}",
                          bt.strategy_name || t("backtest.title"),
                        )}
                        className="flex h-9 w-9 items-center justify-center rounded-xl text-as-muted hover:bg-white"
                      >
                        <ArrowUpRight className="h-4 w-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <p className="text-[11px] leading-5 text-as-muted">
        {t("backtest.collection.footnote")}
      </p>
    </div>
  );
}
