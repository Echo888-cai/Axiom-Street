"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { RadioTower } from "lucide-react";
import { api } from "@/lib/api";
import type { PaperSession } from "@/lib/api/paper";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";

/** P5 持续模拟会话卡片：观察期进度诚实展示（30 交易日且需有成交），带 halt/kill。 */
export function PaperSessionCard({ strategyId }: { strategyId: string }) {
  const qc = useQueryClient();
  const [createdId, setCreatedId] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () =>
      api.createPaperSession({ strategy_id: strategyId, initial_cash: 100_000 }),
    onSuccess: (session: PaperSession) => {
      setCreatedId(session.id);
      toast(`会话已创建：${session.name}`, "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });
  const sessionId = createdId;
  const statusQuery = useQuery({
    queryKey: ["paper-session-status", sessionId],
    queryFn: () => api.observationStatus(sessionId!),
    enabled: Boolean(sessionId),
    refetchInterval: 10_000,
  });

  const halt = useMutation({ mutationFn: (id: string) => api.haltPaperSession(id) });
  const resume = useMutation({ mutationFn: (id: string) => api.resumePaperSession(id) });
  const kill = useMutation({
    mutationFn: (enabled: boolean) => api.toggleKillSwitch(sessionId!, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["paper-session", sessionId] }),
  });

  const status = statusQuery.data;
  return (
    <section className="rounded-as border border-as-border bg-as-bg p-5 shadow-as">
      <div className="flex items-center gap-2">
        <RadioTower className="h-4 w-4 text-as-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold">持续模拟会话（P5）</h2>
      </div>
      {!sessionId ? (
        <p className="mt-3 text-xs text-as-muted">
          尚未创建会话。创建后会冻结当前策略版本，行情驱动的信号按 bar 幂等进入执行。
        </p>
      ) : (
        <div className="mt-3 space-y-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={status?.sufficient ? "green" : "amber"}>
              观察期 {status?.observation_days ?? 0}/{status?.observation_target ?? 30} 交易日
            </Badge>
            <Badge tone={status?.executed_signals ? "blue" : "neutral"}>
              成交信号 {status?.executed_signals ?? 0}
            </Badge>
            {status && !status.sufficient ? (
              <span className="text-amber-700">未达观察要求：30 个交易日且需有成交。</span>
            ) : (
              <span className="text-as-positive">观察期已覆盖，可进入下一阶段。</span>
            )}
          </div>
          <p className="text-as-muted">{status?.note}</p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => halt.mutate(sessionId)}>
              暂停开仓（halt）
            </Button>
            <Button size="sm" variant="secondary" onClick={() => resume.mutate(sessionId)}>
              恢复
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => kill.mutate(true)}
              disabled={kill.isPending}
            >
              Kill Switch
            </Button>
          </div>
          <p className="text-[10px] text-as-muted">
            halt/kill 只阻断新增风险，不自动平仓；迟到/修订 bar 与重复 bar 都不会重复下单。
          </p>
        </div>
      )}
      {!sessionId && (
        <Button size="sm" className="mt-3" disabled={!strategyId} onClick={() => create.mutate()}>
          {create.isPending ? "创建中…" : "创建模拟会话"}
        </Button>
      )}
    </section>
  );
}