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

const FILTERS = [
  { id: "ALL", label: "全部记录" },
  { id: "COMPLETED", label: "已完成" },
  { id: "RUNNING", label: "进行中" },
  { id: "FAILED", label: "失败" },
];
const ACTIVE = ["QUEUED", "STARTING", "RUNNING"];

export default function BacktestCollection() {
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
  const stats = [
    { label: "研究记录", count: data?.length, icon: Archive },
    {
      label: "已完成回测",
      count: data?.filter((b) => b.status === "COMPLETED").length,
      icon: CheckCheck,
    },
    {
      label: "正在进行",
      count: data?.filter((b) => ACTIVE.includes(b.status)).length,
      icon: Timer,
    },
  ];
  return (
    <div className="space-y-7 as-enter">
      <PageHeader
        title="回测工作室"
        description="回到历史之中，检验每一个关于未来的假设。"
        action={
          <Link
            href="/strategies"
            className="as-button-primary inline-flex min-h-11 items-center gap-2 rounded-xl px-4 text-xs text-white"
          >
            <Plus className="h-4 w-4" /> 运行新回测
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
        <Tabs value={filter} onChange={setFilter} items={FILTERS} />
        <div className="relative w-full sm:w-60">
          <Search className="pointer-events-none absolute left-3 top-3.5 h-3.5 w-3.5 text-as-muted" />
          <Input
            aria-label="搜索回测"
            placeholder="搜索策略或基准…"
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
            title="暂时无法读取回测记录"
            description="请检查研究服务的连接状态。"
            action={
              <Button variant="secondary" onClick={() => refetch()}>
                重新连接
              </Button>
            }
          />
        ) : !data?.length ? (
          <div className="py-10">
            <EmptyState
              icon={LineChart}
              title="每一次验证，都让你更接近答案"
              description="从策略实验室发起第一次回测。冻结数据、执行参数与完整结果，会在这里汇集。"
              action={
                <Link
                  href="/strategies"
                  className="as-button-secondary inline-flex min-h-10 items-center gap-2 rounded-xl border border-as-border px-4 text-xs"
                >
                  打开策略实验室 <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              }
            />
          </div>
        ) : !rows.length ? (
          <EmptyState
            icon={Search}
            title="当前条件下没有回测"
            action={
              <Button
                variant="ghost"
                onClick={() => {
                  setFilter("ALL");
                  setSearch("");
                }}
              >
                重置筛选
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[660px] text-left">
              <thead className="border-b border-as-border bg-as-secondary/45 text-[10px] font-normal text-as-muted">
                <tr>
                  {[
                    "研究 / 策略",
                    "回测区间",
                    "累计收益",
                    "夏普比率",
                    "最大回撤",
                    "状态",
                    "",
                  ].map((label, i) => (
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
                        {bt.strategy_name || "未命名策略"}
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
                        aria-label={`查看 ${bt.strategy_name || "回测"} 详情`}
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
        每次回测绑定固定的数据快照和引擎版本，让结论能够被重现。
      </p>
    </div>
  );
}
