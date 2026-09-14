"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Loader2, X } from "lucide-react";
import { api } from "@/lib/api";
import { BACKTEST_TONE, labelStatus, labelStep } from "@/lib/labels";
import { formatRelative } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";
import type { Task, TaskKind } from "@/lib/api/tasks";

const KIND_LABEL: Record<TaskKind, string> = {
  backtest: "回测",
  validation: "验证",
  ingest: "摄取",
  copilot: "研究助手",
};

const KIND_TONE: Record<TaskKind, "blue" | "amber" | "neutral" | "green"> = {
  backtest: "blue",
  validation: "amber",
  ingest: "green",
  copilot: "neutral",
};

/** P2.2 统一任务抽屉：排队/运行/取消/失败可回看，跨页保留。 */
export function TaskDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const tasks = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api.listTasks(),
    refetchInterval: 10_000,
    enabled: open,
  });
  const cancel = useMutation({
    mutationFn: (id: string) => api.cancelTask(id),
    onSuccess: () => {
      toast("已请求取消，任务将以取消状态结束。", "ok");
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["backtests"] });
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  if (!open) return null;
  const rows = tasks.data ?? [];

  return (
    <>
      <button
        type="button"
        aria-label="关闭任务中心"
        onClick={onClose}
        className="fixed inset-0 z-20 cursor-default"
      />
      <section
        aria-label="任务中心"
        className="as-glass absolute right-0 top-12 z-30 flex max-h-[70vh] w-[26rem] max-w-[calc(100vw-24px)] flex-col overflow-hidden rounded-2xl border border-as-border shadow-as-lg as-scale-in"
      >
        <div className="flex items-center justify-between border-b border-as-border p-4">
          <div>
            <div className="text-xs font-semibold">任务中心</div>
            <p className="mt-0.5 text-[10px] text-as-muted">
              回测、验证、行情摄取与研究助手的统一进度
            </p>
          </div>
          <button
            type="button"
            aria-label="关闭"
            onClick={onClose}
            className="as-action-icon"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {tasks.isError ? (
          <p className="p-6 text-xs leading-relaxed text-as-muted">
            暂时无法读取任务：{tasks.error.message}
          </p>
        ) : tasks.isLoading && !rows.length ? (
          <p className="p-6 text-xs text-as-muted">正在读取任务…</p>
        ) : !rows.length ? (
          <p className="p-6 text-xs leading-relaxed text-as-muted">
            还没有执行任务。运行一次回测、发起验证或拉取行情后会出现在这里。
          </p>
        ) : (
          <ul className="max-h-[52vh] overflow-auto p-2">
            {rows.map((task) => (
              <TaskRow
                key={`${task.kind}-${task.id}`}
                task={task}
                cancelling={cancel.isPending && cancel.variables === task.id}
                onCancel={() => cancel.mutate(task.id)}
                onOpen={() => {
                  onClose();
                  if (task.ref) router.push(task.ref);
                }}
              />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

function TaskRow({
  task,
  cancelling,
  onCancel,
  onOpen,
}: {
  task: Task;
  cancelling: boolean;
  onCancel: () => void;
  onOpen: () => void;
}) {
  const terminal = ["COMPLETED", "FAILED", "CANCELLED"].includes(task.status);
  const tone = BACKTEST_TONE[task.status] || "neutral";
  return (
    <li className="rounded-xl px-3 py-3 hover:bg-white">
      <div className="flex items-center justify-between gap-2">
        <button type="button" onClick={onOpen} className="min-w-0 text-left">
          <span className="flex items-center gap-2">
            <Badge tone={KIND_TONE[task.kind]}>{KIND_LABEL[task.kind]}</Badge>
            <span className="truncate text-xs">{task.title}</span>
          </span>
        </button>
        <Badge tone={tone}>{labelStatus(task.status)}</Badge>
      </div>
      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span className="truncate text-[10px] text-as-muted">
          {labelStep(task.progress_step) || "—"} ·{" "}
          {formatRelative(task.finished_at || task.created_at)}
        </span>
        {!terminal && task.cancelable && (
          <button
            type="button"
            onClick={onCancel}
            disabled={cancelling}
            className="as-action-icon"
            aria-label={`取消 ${task.title}`}
          >
            {cancelling ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <X className="h-3.5 w-3.5" />
            )}
          </button>
        )}
      </div>
    </li>
  );
}