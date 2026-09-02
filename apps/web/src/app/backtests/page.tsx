"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, LineChart } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { BACKTEST_TONE, labelStatus } from "@/lib/labels";
import { formatNumber, formatPct } from "@/lib/utils";

const FILTERS = [
  { id: "ALL", label: "全部" },
  { id: "COMPLETED", label: "已完成" },
  { id: "RUNNING", label: "进行中" },
  { id: "FAILED", label: "失败" },
];

export default function BacktestsPage() {
  const [filter, setFilter] = useState("ALL");
  const { data, isLoading, error } = useQuery({
    queryKey: ["backtests"],
    queryFn: api.listBacktests,
    refetchInterval: 3000,
  });

  const rows = useMemo(() => {
    const items = data || [];
    if (filter === "ALL") return items;
    if (filter === "RUNNING") {
      return items.filter((b) => ["QUEUED", "STARTING", "RUNNING"].includes(b.status));
    }
    return items.filter((b) => b.status === filter);
  }, [data, filter]);

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="回测"
        description="使用冻结数据与固定引擎版本的可复现 LEAN 回测。"
        action={
          <Link href="/strategies">
            <Button variant="secondary">策略实验室</Button>
          </Link>
        }
      />

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState title="API 未连接" description="请先启动 API（端口 8000）。" />
        </Card>
      ) : !data?.length ? (
        <Card className="min-h-[280px]">
          <EmptyState
            icon={LineChart}
            title="还没有回测记录"
            description="创建 SPY 200 日均线策略，然后运行第一次可复现回测。"
            action={
              <Link href="/strategies">
                <Button size="sm">前往策略实验室</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          <Tabs value={filter} onChange={setFilter} items={FILTERS} />
          <div className="space-y-3 as-stagger">
            {rows.map((bt) => (
              <Link key={bt.id} href={`/backtests/${bt.id}`}>
                <Card hover className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-as-text">
                      {bt.strategy_name || "未命名策略"}
                      {bt.version_number ? ` · v${bt.version_number}` : ""}
                    </div>
                    <div className="mt-1 text-xs text-as-muted">
                      {bt.start_date} → {bt.end_date}
                      {bt.engine_version ? ` · ${bt.engine_version}` : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-5">
                    {bt.status === "COMPLETED" ? (
                      <div className="hidden items-center gap-5 sm:flex">
                        <Metric label="收益" value={formatPct(bt.total_return)} pos={bt.total_return} />
                        <Metric label="夏普" value={formatNumber(bt.sharpe)} />
                        <Metric label="回撤" value={formatPct(bt.max_drawdown)} neg />
                      </div>
                    ) : null}
                    <Badge tone={BACKTEST_TONE[bt.status] || "blue"}>
                      {labelStatus(bt.status)}
                    </Badge>
                    <ChevronRight className="h-4 w-4 text-as-muted" />
                  </div>
                </Card>
              </Link>
            ))}
            {!rows.length ? (
              <p className="py-8 text-center text-sm text-as-muted">这一筛选下没有记录。</p>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  pos,
  neg,
}: {
  label: string;
  value: string;
  pos?: number | null;
  neg?: boolean;
}) {
  const tone =
    neg ? "text-as-negative" : pos != null && pos >= 0 ? "text-as-positive" : pos != null ? "text-as-negative" : "text-as-text";
  return (
    <div className="text-right">
      <div className="text-[10px] text-as-muted">{label}</div>
      <div className={`text-xs tabular ${tone}`}>{value}</div>
    </div>
  );
}
