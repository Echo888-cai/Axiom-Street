"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { FileBarChart2 } from "lucide-react";
import { api, type ResearchNote, type Strategy } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { toast } from "@/components/ui/toast";
import { cn, formatRelative } from "@/lib/utils";

const SECTIONS: Array<{
  key: "hypothesis" | "method" | "conclusion" | "failure_modes";
  label: string;
  hint: string;
  placeholder: string;
  rows: number;
}> = [
  {
    key: "hypothesis",
    label: "假设",
    hint: "这条策略为什么应该赚钱。来自构建器时会预填。",
    placeholder: "在什么市场状态下、凭什么机制产生期望为正的超额收益。",
    rows: 5,
  },
  {
    key: "method",
    label: "检验",
    hint: "实际跑过的回测与验证闸门，不要写计划中的检验。",
    placeholder: "全样本回测区间、DSR、Walk-forward、PBO、敏感性……写做过的，不写打算做的。",
    rows: 6,
  },
  {
    key: "conclusion",
    label: "结论",
    hint: "对假设的裁决。VALIDATED 只能由验证管线给出。",
    placeholder: "假设成立、被削弱，还是被证伪。不要把原始夏普写成结论。",
    rows: 5,
  },
  {
    key: "failure_modes",
    label: "失效模式",
    hint: "什么情况下这条策略会坏掉。",
    placeholder: "趋势反转、成本抬升、制度切换、容量……",
    rows: 5,
  },
];

export function ResearchDesk() {
  const qc = useQueryClient();
  const params = useSearchParams();
  const initialStrategy = params.get("strategy_id") || "";
  const initialBacktest = params.get("backtest_id") || "";
  const [strategyId, setStrategyId] = useState(initialStrategy);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Partial<ResearchNote>>({});
  const [confirmDelete, setConfirmDelete] = useState(false);

  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.listStrategies });
  const notes = useQuery({
    queryKey: ["research-notes", strategyId || "all"],
    queryFn: () => api.listResearchNotes(strategyId ? { strategy_id: strategyId } : undefined),
  });

  const selected = useMemo(
    () => (notes.data?.items || []).find((n) => n.id === activeId) || null,
    [activeId, notes.data],
  );

  useEffect(() => {
    if (selected) {
      setDraft(selected);
      return;
    }
    setDraft({});
  }, [selected]);

  useEffect(() => {
    if (activeId || !notes.data?.items.length) return;
    setActiveId(notes.data.items[0].id);
  }, [activeId, notes.data]);

  const dirty = useMemo(() => {
    if (!selected) return false;
    return (
      (draft.title ?? "") !== selected.title ||
      (draft.hypothesis ?? "") !== selected.hypothesis ||
      (draft.method ?? "") !== selected.method ||
      (draft.conclusion ?? "") !== selected.conclusion ||
      (draft.failure_modes ?? "") !== selected.failure_modes
    );
  }, [draft, selected]);

  const create = useMutation({
    mutationFn: () =>
      api.createResearchNote({
        strategy_id: strategyId,
        backtest_id: initialBacktest || undefined,
      }),
    onSuccess: (note) => {
      qc.invalidateQueries({ queryKey: ["research-notes"] });
      setActiveId(note.id);
      toast("已从策略假设创建笔记", "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const save = useMutation({
    mutationFn: () =>
      api.updateResearchNote(selected!.id, {
        title: draft.title,
        hypothesis: draft.hypothesis,
        method: draft.method,
        conclusion: draft.conclusion,
        failure_modes: draft.failure_modes,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["research-notes"] });
      toast("笔记已保存", "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteResearchNote(selected!.id),
    onSuccess: () => {
      setActiveId(null);
      qc.invalidateQueries({ queryKey: ["research-notes"] });
      toast("笔记已删除", "info");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty && selected) save.mutate();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dirty, selected, save]);

  const strategyName = (strategies.data || []).find((s) => s.id === strategyId)?.name;

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4 as-enter">
      <PageHeader
        title="研究笔记"
        description="假设 → 检验 → 结论 → 失效模式。这里不生成回测数字，也不改验证状态。"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
              策略
              <select
                className="h-9 min-w-[180px] rounded-lg border border-as-border bg-as-bg px-2 text-sm text-as-text outline-none focus:border-as-primary/40"
                value={strategyId}
                onChange={(e) => {
                  setStrategyId(e.target.value);
                  setActiveId(null);
                }}
              >
                <option value="">全部笔记</option>
                {(strategies.data || []).map((s: Strategy) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <Button
              onClick={() => create.mutate()}
              disabled={!strategyId || create.isPending}
            >
              {create.isPending ? "创建中…" : "新建笔记"}
            </Button>
          </div>
        }
      />

      {!strategies.data?.length && !strategies.isLoading ? (
        <Card className="min-h-[280px]">
          <EmptyState
            icon={FileBarChart2}
            title="还没有策略"
            description="研究笔记挂在策略上。先到实验室写一条假设。"
            action={
              <Link href="/strategies">
                <Button size="sm">策略实验室</Button>
              </Link>
            }
          />
        </Card>
      ) : notes.isError ? (
        <Card className="min-h-[280px]">
          <EmptyState
            icon={FileBarChart2}
            title="研究笔记接口不可用"
            description={
              notes.error instanceof Error
                ? `当前 API 没有研究笔记接口（${notes.error.message}）。需要跑过 Alembic 0008 的 API 进程。`
                : "API 还没有 research-notes。需要带 0008 迁移的 API 进程。"
            }
          />
        </Card>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-12 gap-4">
          <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-3">
            <div className="border-b border-as-border px-4 py-3 text-sm font-medium">目录</div>
            <ul className="flex-1 space-y-1 overflow-auto p-3">
              {(notes.data?.items || []).map((note) => (
                <li key={note.id}>
                  <button
                    type="button"
                    onClick={() => setActiveId(note.id)}
                    className={cn(
                      "w-full cursor-pointer rounded-lg px-3 py-2.5 text-left transition-colors duration-as",
                      note.id === activeId ? "bg-[rgba(22,119,255,0.08)]" : "hover:bg-as-secondary",
                    )}
                  >
                    <div className="truncate text-sm font-medium text-as-text">{note.title}</div>
                    <p className="mt-0.5 truncate text-[11px] text-as-muted">
                      {note.hypothesis || "假设还是空的"} · {formatRelative(note.updated_at)}
                    </p>
                  </button>
                </li>
              ))}
              {!notes.data?.items.length ? (
                <p className="px-2 py-8 text-center text-xs text-as-muted">
                  {strategyId ? "这篇策略还没有笔记。" : "选择策略后新建。"}
                </p>
              ) : null}
            </ul>
          </Card>

          <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-9">
            {!selected ? (
              <EmptyState
                icon={FileBarChart2}
                title="选择或新建一篇笔记"
                description="假设字段会从策略构建器带过来。其余三栏要你自己写，系统不会代填结论。"
              />
            ) : (
              <div className="flex min-h-0 flex-1 flex-col">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-as-border px-5 py-3">
                  <div className="min-w-0 flex-1">
                    <Input
                      value={draft.title ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
                      className="h-10 border-transparent px-0 text-[18px] font-semibold shadow-none focus:border-as-primary/30"
                    />
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-as-muted">
                      {strategyName ? <span>{strategyName}</span> : null}
                      {selected.backtest_id ? (
                        <Link
                          href={`/backtests/${selected.backtest_id}`}
                          className="text-as-primary hover:underline"
                        >
                          关联 tearsheet
                        </Link>
                      ) : initialBacktest ? (
                        <Badge tone="blue">将关联本次回测</Badge>
                      ) : null}
                      {dirty ? <Badge tone="amber">未保存</Badge> : <span>⌘S 保存</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={!dirty || save.isPending}
                      onClick={() => save.mutate()}
                    >
                      {save.isPending ? "保存中…" : "保存"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
                      删除
                    </Button>
                  </div>
                </div>
                <div className="min-h-0 flex-1 space-y-6 overflow-auto px-5 py-5">
                  {SECTIONS.map((section) => (
                    <label key={section.key} className="block">
                      <div className="mb-1.5 flex items-baseline justify-between gap-3">
                        <span className="text-sm font-medium text-as-text">{section.label}</span>
                        <span className="text-[11px] text-as-muted">{section.hint}</span>
                      </div>
                      <textarea
                        value={String(draft[section.key] ?? "")}
                        onChange={(e) => setDraft((d) => ({ ...d, [section.key]: e.target.value }))}
                        rows={section.rows}
                        placeholder={section.placeholder}
                        className="w-full resize-y rounded-lg border border-as-border bg-as-bg px-3 py-2.5 text-sm leading-relaxed text-as-text outline-none placeholder:text-as-muted focus:border-as-primary/40 focus-visible:ring-2 focus-visible:ring-as-primary/20"
                      />
                    </label>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="删除这篇研究笔记？"
        description="删除后无法从界面恢复。回测与验证记录不受影响。"
        confirmLabel="删除笔记"
        danger
        onConfirm={() => remove.mutate()}
        onClose={() => setConfirmDelete(false)}
      />
    </div>
  );
}
