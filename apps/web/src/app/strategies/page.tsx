"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { labelStatus } from "@/lib/labels";
import { toast } from "@/components/ui/toast";
import { formatRelative } from "@/lib/utils";

export default function StrategiesPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["strategies"],
    queryFn: api.listStrategies,
  });

  const create = useMutation({
    mutationFn: () =>
      api.createStrategy({
        name: "SPY 200日均线",
        description: "价格站上 200 日均线持有 SPY，跌破则空仓。",
      }),
    onSuccess: (strategy) => {
      qc.invalidateQueries({ queryKey: ["strategies"] });
      toast("策略已创建", "ok");
      router.push(`/strategies/${strategy.id}`);
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  return (
    <div className="space-y-6 aq-enter">
      <PageHeader
        title="策略实验室"
        description="把投资假设变成可验证、可复现的量化策略。"
        action={
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending ? "创建中…" : "创建 SPY 200日均线"}
          </Button>
        }
      />

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-aq-secondary" />
      ) : error ? (
        <Card>
          <EmptyState title="API 未连接" description="请先启动 FastAPI 服务（端口 8000）。" />
        </Card>
      ) : !data?.length ? (
        <Card className="min-h-[320px]">
          <EmptyState
            icon={FlaskConical}
            title="把投资假设变成可验证的量化策略"
            description="例如：SPY 站上 200 日均线持有，跌破则空仓。"
            action={
              <Button onClick={() => create.mutate()} disabled={create.isPending}>
                用模板创建
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-3 aq-stagger">
          {data.map((s) => (
            <Link key={s.id} href={`/strategies/${s.id}`}>
              <Card hover className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-medium text-aq-text">{s.name}</div>
                    <Badge tone="blue">{s.benchmark}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-aq-muted">{s.description || "暂无描述"}</div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="hidden text-right sm:block">
                    <div className="text-[11px] text-aq-muted">v{s.latest_version?.version ?? 1}</div>
                    <div className="text-[11px] text-aq-muted">{formatRelative(s.updated_at)}</div>
                  </div>
                  <Badge tone="neutral">{labelStatus(s.status)}</Badge>
                  <ChevronRight className="h-4 w-4 text-aq-muted" />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
