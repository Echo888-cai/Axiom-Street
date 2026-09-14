"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { FileBarChart2 } from "lucide-react";
import { api, type ResearchExport, type ResearchNote, type Strategy } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { toast } from "@/components/ui/toast";
import { cn, formatRelative } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { NoteFields } from "./note-fields";

export function ResearchDesk() {
  const qc = useQueryClient();
  const t = useT();
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
      (draft.failure_modes ?? "") !== selected.failure_modes ||
      JSON.stringify(draft.drafted_by ?? {}) !== JSON.stringify(selected.drafted_by ?? {})
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
      toast(t("common.research.createFromStrategyToast"), "ok");
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
        drafted_by: draft.drafted_by as Record<string, string> | undefined,
        evidence: draft.evidence as Record<string, unknown> | undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["research-notes"] });
      toast(t("common.research.savedToast"), "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteResearchNote(selected!.id),
    onSuccess: () => {
      setActiveId(null);
      qc.invalidateQueries({ queryKey: ["research-notes"] });
      toast(t("common.research.deletedToast"), "info");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  // P2.4 证据清单（服务端解析）与冻结导出（不可变快照）
  const evidence = useQuery({
    queryKey: ["research-evidence", selected?.id],
    queryFn: () => api.getResearchEvidence(selected!.id),
    enabled: Boolean(selected?.id),
  });
  const exportsList = useQuery({
    queryKey: ["research-exports", selected?.id],
    queryFn: () => api.listResearchExports(selected!.id),
    enabled: Boolean(selected?.id),
  });
  const exportNote = useMutation({
    mutationFn: () => api.exportResearchNote(selected!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["research-exports", selected?.id] });
      toast("导出已冻结：此后编辑不会改写这份导出。", "ok");
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
    <div className="flex min-h-[calc(100dvh-12rem)] flex-col gap-6 as-enter">
      <PageHeader
        title={t("common.researchNote")}
        description="记下想法、证据与结论。"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
              {t("common.research.strategyLabel")}
              <select
                className="h-9 min-w-[180px] rounded-lg border border-as-border bg-as-bg px-2 text-sm text-as-text outline-none focus:border-as-primary/40"
                value={strategyId}
                onChange={(e) => {
                  setStrategyId(e.target.value);
                  setActiveId(null);
                }}
              >
                <option value="">{t("common.research.allNotes")}</option>
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
              {create.isPending ? t("common.creating") : t("common.research.newNote")}
            </Button>
          </div>
        }
      />

      {!strategies.data?.length && !strategies.isLoading ? (
        <Card className="min-h-[280px]">
          <EmptyState
            icon={FileBarChart2}
            title={t("common.research.noStrategiesTitle")}
            description={t("common.research.noStrategiesDesc")}
            action={
              <Link href="/strategies">
                <Button size="sm">{t("common.research.strategyLab")}</Button>
              </Link>
            }
          />
        </Card>
      ) : notes.isError ? (
        <Card className="min-h-[280px]">
          <EmptyState
            icon={FileBarChart2}
            title={t("common.research.apiUnavailableTitle")}
            description={
              notes.error instanceof Error
                ? t("common.research.apiErrorTemplate")
                    .split("{message}")
                    .join(notes.error.message)
                : t("common.research.apiMissing")
            }
          />
        </Card>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-12 gap-4">
          <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-3">
            <div className="border-b border-as-border px-4 py-3 text-sm font-medium">{t("common.research.toc")}</div>
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
                    <p className="mt-1 text-xs text-as-muted">{formatRelative(note.updated_at)}</p>
                  </button>
                </li>
              ))}
              {!notes.data?.items.length ? (
                <p className="px-2 py-8 text-center text-xs text-as-muted">
                  {strategyId
                    ? t("common.research.strategyNoNotes")
                    : t("common.research.selectThenCreate")}
                </p>
              ) : null}
            </ul>
          </Card>

          <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-9">
            {!selected ? (
              <EmptyState
                icon={FileBarChart2}
                title={t("common.research.selectNoteTitle")}
                description={t("common.research.selectNoteDesc")}
              />
            ) : (
              <div className="flex min-h-0 flex-1 flex-col">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-as-border px-5 py-3">
                  <div className="min-w-0 flex-1">
                    <Input
                      aria-label="笔记标题"
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
                          {t("common.research.linkTearsheet")}
                        </Link>
                      ) : initialBacktest ? (
                        <Badge tone="blue">{t("common.research.willLinkBacktest")}</Badge>
                      ) : null}
                      {dirty ? (
                        <Badge tone="amber">{t("common.research.unsaved")}</Badge>
                      ) : (
                        <span>{t("common.research.cmdSave")}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={!dirty || save.isPending}
                      onClick={() => save.mutate()}
                    >
                      {save.isPending ? t("common.saving") : t("common.save")}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
                      {t("common.delete")}
                    </Button>
                  </div>
                </div>
                <NoteFields
                  draft={draft}
                  onChange={(key, value) => setDraft((d) => ({ ...d, [key]: value }))}
                  draftedBy={(draft.drafted_by as Record<string, string> | undefined) ?? {}}
                  onDraftedBy={(key, source) =>
                    setDraft((d) => ({
                      ...d,
                      drafted_by: {
                        ...((d.drafted_by as Record<string, string> | undefined) ?? {}),
                        [key]: source,
                      },
                    }))
                  }
                />
                <EvidencePanel
                  noteId={selected.id}
                  items={(evidence.data?.items ?? []) as EvidenceItem[]}
                  loading={evidence.isLoading}
                  exporting={exportNote.isPending}
                  exports={(exportsList.data ?? []) as ResearchExport[]}
                  onExport={() => exportNote.mutate()}
                />
              </div>
            )}
          </Card>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title={t("common.research.deleteNoteTitle")}
        description={t("common.research.deleteNoteDesc")}
        confirmLabel={t("common.research.deleteNoteLabel")}
        danger
        onConfirm={() => remove.mutate()}
        onClose={() => setConfirmDelete(false)}
      />
    </div>
  );
}


type EvidenceItem = { kind: string; id: string; label?: string; status?: string };

function capturedAtOf(exp: ResearchExport): string {
  const evidence = (exp.payload as { evidence?: { captured_at?: string } }).evidence;
  return (evidence?.captured_at ?? "").slice(0, 19).replace("T", " ");
}

function EvidencePanel({
  noteId,
  items,
  loading,
  exporting,
  exports,
  onExport,
}: {
  noteId: string;
  items: EvidenceItem[];
  loading: boolean;
  exporting: boolean;
  exports: ResearchExport[];
  onExport: () => void;
}) {
  return (
    <div className="space-y-4 border-t border-as-border p-5 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs font-medium">证据清单</div>
        <Button variant="secondary" size="sm" onClick={onExport} disabled={exporting}>
          {exporting ? "冻结中…" : "导出（冻结当前证据）"}
        </Button>
      </div>
      {loading ? (
        <p className="text-xs text-as-muted">正在解析证据…</p>
      ) : items.length === 0 ? (
        <p className="text-xs leading-relaxed text-as-muted">
          尚未关联版本/回测/验证。绑定后，第三人可凭此清单找到输入结果。
        </p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item) => (
            <li key={`${item.kind}-${item.id}`} className="flex items-center gap-2 text-xs">
              <Badge tone={item.kind === "version" ? "blue" : item.kind === "backtest" ? "green" : "amber"}>
                {item.kind === "version" ? "版本" : item.kind === "backtest" ? "回测" : "验证"}
              </Badge>
              <span className="truncate text-as-text">{item.label ?? item.id}</span>
              {item.status ? <span className="text-as-muted">{item.status}</span> : null}
              <span className="ml-auto tabular text-[10px] text-as-muted">{item.id.slice(0, 8)}…</span>
            </li>
          ))}
        </ul>
      )}
      <div className="text-[11px] text-as-muted">
        每次「导出」都会把当时的证据清单与时间固化为不可变快照；之后的编辑不会改写旧导出（笔记 {noteId.slice(0, 8)}…）。
      </div>
      {exports.length > 0 ? (
        <ul className="space-y-1">
          {exports.map((exp) => (
            <li key={exp.id} className="flex items-center gap-2 text-[11px] text-as-muted">
              <Badge tone="neutral">冻结导出 #{exports.length > 1 ? String(exports.indexOf(exp) + 1) : "1"}</Badge>
              <span>{formatRelative(exp.created_at)}</span>
              <span className="ml-auto tabular">{capturedAtOf(exp)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
