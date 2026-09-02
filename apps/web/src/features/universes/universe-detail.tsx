"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { toast } from "@/components/ui/toast";

function spanLabel(from: string, to: string | null): string {
  return `${from.slice(0, 10)} → ${to ? to.slice(0, 10) : "仍在池中"}`;
}

export function UniverseDetail({ universeId }: { universeId: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const universe = useQuery({
    queryKey: ["universe", universeId],
    queryFn: () => api.getUniverse(universeId),
  });
  const [symbol, setSymbol] = useState("");
  const [from, setFrom] = useState("2010-01-04");
  const [to, setTo] = useState("");
  const [infer, setInfer] = useState(false);
  const [asOf, setAsOf] = useState("2018-03-24");
  const [preview, setPreview] = useState<string[] | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["universe", universeId] });
    qc.invalidateQueries({ queryKey: ["universes"] });
  };

  const add = useMutation({
    mutationFn: () =>
      api.addUniverseMember(universeId, {
        symbol: symbol.trim().toUpperCase(),
        effective_from: from,
        effective_to: infer || !to ? null : to,
        infer_effective_to_from_data: infer,
      }),
    onSuccess: () => {
      invalidate();
      setSymbol("");
      setTo("");
      setInfer(false);
      setPreview(null);
      toast("成分已加入", "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const removeMember = useMutation({
    mutationFn: (memberId: string) => api.deleteUniverseMember(universeId, memberId),
    onSuccess: () => {
      invalidate();
      setPreview(null);
      toast("成分已移除", "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const removeUniverse = useMutation({
    mutationFn: () => api.deleteUniverse(universeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["universes"] });
      toast("标的池已删除", "info");
      router.push("/universes");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const runPreview = useMutation({
    mutationFn: () => api.previewUniverse(universeId, { as_of: asOf }),
    onSuccess: (result) => setPreview(result.symbols),
    onError: (err: Error) => toast(err.message, "err"),
  });

  if (universe.isLoading) {
    return <Card className="h-40 animate-pulse bg-as-secondary" />;
  }
  if (universe.error || !universe.data) {
    return (
      <Card>
        <EmptyState title="找不到这个标的池" description="它可能已被删除。" />
      </Card>
    );
  }

  const row = universe.data;
  const members = [...row.members].sort((a, b) =>
    a.symbol === b.symbol
      ? a.effective_from.localeCompare(b.effective_from)
      : a.symbol.localeCompare(b.symbol),
  );

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        crumbs={[
          { href: "/", label: "首页" },
          { href: "/universes", label: "标的池" },
        ]}
        title={row.name}
        description={
          row.description ||
          "成分区间两端都包含。退市日之后该标的不得再进入回测。"
        }
        action={
          <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
            删除标的池
          </Button>
        }
      />

      <Card>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (symbol.trim()) add.mutate();
          }}
        >
          <label className="space-y-1 text-[11px] text-as-muted">
            标的
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="SPY"
              className="w-28 uppercase"
            />
          </label>
          <label className="space-y-1 text-[11px] text-as-muted">
            进入日
            <Input type="date" className="w-[148px]" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="space-y-1 text-[11px] text-as-muted">
            退出日（可空）
            <Input
              type="date"
              className="w-[148px]"
              value={to}
              disabled={infer}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
          <label className="flex h-9 items-center gap-2 text-xs text-as-muted">
            <input
              type="checkbox"
              className="accent-[#1677FF]"
              checked={infer}
              onChange={(e) => setInfer(e.target.checked)}
            />
            从行情推断退市日
          </label>
          <Button type="submit" disabled={add.isPending || !symbol.trim()}>
            {add.isPending ? "加入中…" : "加入成分"}
          </Button>
        </form>
        <p className="mt-3 text-xs text-as-muted">
          推断退市需要该标的已摄取。最后一根 K 线若早于 14 个自然日，则记为 inclusive 退出日；否则视为仍在上市。
        </p>
      </Card>

      <Card className="p-0">
        <div className="border-b border-as-border px-5 py-3 text-sm font-medium">成分</div>
        {!members.length ? (
          <EmptyState
            title="这个标的池还没有成分"
            description="没有成分的区间无法开跑回测。加入至少一支股票，并写上有效区间。"
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-as-muted">
              <tr className="border-b border-as-border">
                <th className="px-5 py-2 font-medium">标的</th>
                <th className="px-5 py-2 font-medium">有效区间</th>
                <th className="px-5 py-2 font-medium">状态</th>
                <th className="px-5 py-2" />
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.id} className="border-b border-as-border last:border-0">
                  <td className="px-5 py-3 font-medium tabular-nums">{member.symbol}</td>
                  <td className="px-5 py-3 tabular-nums text-as-muted">
                    {spanLabel(member.effective_from, member.effective_to)}
                  </td>
                  <td className="px-5 py-3">
                    {member.effective_to ? (
                      <Badge tone="amber">已退出</Badge>
                    ) : (
                      <Badge tone="green">仍在池中</Badge>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeMember.mutate(member.id)}
                      disabled={removeMember.isPending}
                    >
                      移除
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card>
        <div className="mb-3 text-sm font-medium">时点预览</div>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            runPreview.mutate();
          }}
        >
          <label className="space-y-1 text-[11px] text-as-muted">
            查询日
            <Input type="date" className="w-[148px]" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          </label>
          <Button type="submit" variant="secondary" disabled={runPreview.isPending}>
            {runPreview.isPending ? "查询中…" : "查看当日成分"}
          </Button>
        </form>
        {preview ? (
          <p className="mt-3 text-sm tabular-nums text-as-text">
            {preview.length ? preview.join(", ") : "该日没有任何成分"}
          </p>
        ) : (
          <p className="mt-3 text-xs text-as-muted">不会编造成分。未查询时不显示结果。</p>
        )}
      </Card>

      <ConfirmDialog
        open={confirmDelete}
        title="删除这个标的池？"
        description="已完成的回测仍保留当时冻结的成分快照。新回测将无法再引用它。"
        confirmLabel="删除"
        danger
        onConfirm={() => removeUniverse.mutate()}
        onClose={() => setConfirmDelete(false)}
      />
    </div>
  );
}
