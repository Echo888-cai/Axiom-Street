import Link from "next/link";
import { ArrowUpRight, ArrowRight, FlaskConical, History } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { BACKTEST_TONE, labelStatus } from "@/lib/labels";
import { formatRelative, formatPct } from "@/lib/utils";
import type { Backtest, Strategy } from "@/lib/api";

export function RecentResearch({
  strategies,
  backtests,
  loading,
  unavailable,
}: {
  strategies: Strategy[];
  backtests: Backtest[];
  loading?: boolean;
  unavailable?: boolean;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
      <Card>
        <CardHeader
          title="我的策略"
          action={
            <Link
              href="/strategies"
              className="flex items-center gap-1 text-[11px] text-as-muted hover:text-as-primary"
            >
              查看全部 <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          }
        />
        {loading ? (
          <Skeleton className="h-36" />
        ) : strategies.length ? (
          <ul className="divide-y divide-as-border">
            {strategies.slice(0, 4).map((s) => (
              <li key={s.id}>
                <Link
                  href={`/strategies/${s.id}`}
                  className="group flex items-center gap-3 rounded-lg py-4 hover:bg-as-secondary/50"
                >
                  <span className="as-icon-well h-9 w-9 rounded-xl">
                    <FlaskConical className="h-4 w-4" strokeWidth={1.5} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-medium">{s.name}</div>
                    <div className="mt-1 text-[10px] text-as-muted">
                      {s.benchmark} <span className="mx-1.5">·</span>{" "}
                      {formatRelative(s.updated_at)}
                    </div>
                  </div>
                  <Badge>{labelStatus(s.status)}</Badge>
                  <ArrowRight className="ml-1 h-3.5 w-3.5 text-as-muted/60 transition-transform group-hover:translate-x-1" />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            icon={FlaskConical}
            title={unavailable ? "等待连接你的策略" : "下一个发现，从这里开始"}
            description={
              unavailable
                ? "连接恢复后，已保存的研究会自动呈现。"
                : "将一个值得探索的想法，保存为你的第一条策略。"
            }
            action={
              <Link href="/strategies" className="text-xs text-as-primary">
                进入策略实验室 →
              </Link>
            }
          />
        )}
      </Card>
      <Card>
        <CardHeader
          title="最近回测"
          action={
            <Link
              href="/backtests"
              className="flex items-center gap-1 text-[11px] text-as-muted hover:text-as-primary"
            >
              全部记录 <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          }
        />
        {loading ? (
          <Skeleton className="h-36" />
        ) : backtests.length ? (
          <ul className="divide-y divide-as-border">
            {backtests.slice(0, 4).map((b) => (
              <li key={b.id}>
                <Link
                  href={`/backtests/${b.id}`}
                  className="flex items-center justify-between gap-3 rounded-lg py-4 hover:bg-as-secondary/50"
                >
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium">
                      {b.strategy_name || "策略回测"}
                    </div>
                    <div className="mt-1.5 text-[10px] text-as-muted">
                      {b.start_date} — {b.end_date}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    <Badge tone={BACKTEST_TONE[b.status] || "neutral"}>
                      {labelStatus(b.status)}
                    </Badge>
                    {b.status === "COMPLETED" && (
                      <span className="text-[10px] tabular text-as-muted">
                        {formatPct(b.total_return)}
                      </span>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            icon={History}
            title={unavailable ? "等待同步研究记录" : "留下一次探索的轨迹"}
            description="每一次回测的结果、参数与数据版本，都将在这里留存。"
          />
        )}
      </Card>
    </div>
  );
}
