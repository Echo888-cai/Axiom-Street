"use client";

import Editor from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { labelStatus } from "@/lib/labels";
import { SPY_200DMA_TEMPLATE } from "@/lib/spy-200dma";
import { toast } from "@/components/ui/toast";
import { BuilderPanel } from "./builder-panel";
import { VersionHistory } from "./version-history";

function friendlyError(message: string): string {
  if (message.includes("Docker is required") || message.includes("Docker")) {
    return "需要 Docker（Colima）才能跑 LEAN 回测。请先执行 colima start，并确认 worker 容器在运行。";
  }
  if (message.includes("AfterMarketClose")) {
    return "当前策略代码使用了已失效的 LEAN API。请点击「恢复模板代码」后再运行回测。";
  }
  return message;
}

export function StrategyLab({ strategyId }: { strategyId: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: strategy, isLoading } = useQuery({
    queryKey: ["strategy", strategyId],
    queryFn: () => api.getStrategy(strategyId),
  });
  const versions = useQuery({
    queryKey: ["versions", strategyId],
    queryFn: () => api.listVersions(strategyId),
  });
  const trialStats = useQuery({
    queryKey: ["trial-stats", strategyId],
    queryFn: () => api.getTrialStats(strategyId),
  });
  const universes = useQuery({
    queryKey: ["universes"],
    queryFn: api.listUniverses,
  });

  const [code, setCode] = useState("");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState("更新策略代码");
  const [startDate, setStartDate] = useState("2018-01-01");
  const [endDate, setEndDate] = useState("2020-12-31");
  const [capital, setCapital] = useState("100000");
  const [universeId, setUniverseId] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState("");
  const [confirmRestore, setConfirmRestore] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (strategy?.latest_version?.code) setCode(strategy.latest_version.code);
    if (strategy?.latest_version?.config) setConfig(strategy.latest_version.config);
    if (strategy?.name) setName(strategy.name);
  }, [strategy?.latest_version?.id, strategy?.name]);

  const dirty = useMemo(() => {
    const latest = strategy?.latest_version;
    if (!latest) return Boolean(code);
    return code !== latest.code || JSON.stringify(config) !== JSON.stringify(latest.config);
  }, [code, config, strategy?.latest_version]);

  useEffect(() => {
    const onBefore = (e: BeforeUnloadEvent) => {
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBefore);
    return () => window.removeEventListener("beforeunload", onBefore);
  }, [dirty]);

  const save = useMutation({
    mutationFn: () =>
      api.createVersion(strategyId, { code, config, commit_message: message }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
      qc.invalidateQueries({ queryKey: ["versions", strategyId] });
      toast("版本已保存", "ok");
    },
    onError: (err: Error) => toast(friendlyError(err.message), "err"),
  });

  const rename = useMutation({
    mutationFn: () => api.updateStrategy(strategyId, { name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
      qc.invalidateQueries({ queryKey: ["strategies"] });
      setEditingName(false);
      toast("名称已更新", "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteStrategy(strategyId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["strategies"] });
      toast("策略已删除", "info");
      router.push("/strategies");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty) save.mutate();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dirty, save]);

  const run = useMutation({
    mutationFn: async () => {
      let versionId = strategy?.latest_version?.id;
      if (!versionId || dirty) {
        const version = await api.createVersion(strategyId, {
          code,
          config,
          commit_message: message || "回测前保存",
        });
        versionId = version.id;
        await qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
        await qc.invalidateQueries({ queryKey: ["versions", strategyId] });
      }
      return api.createBacktest({
        strategy_version_id: versionId!,
        start_date: startDate,
        end_date: endDate,
        benchmark: strategy?.benchmark || "SPY",
        initial_capital: Number(capital) || 100000,
        ...(universeId ? { universe_id: universeId } : {}),
      });
    },
    onSuccess: (bt) => {
      toast("回测已提交", "ok");
      router.push(`/backtests/${bt.id}`);
    },
    onError: (err: Error) => toast(friendlyError(err.message), "err"),
  });

  if (isLoading || !strategy) {
    return <Card className="h-[70vh] animate-pulse bg-aq-secondary" />;
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4 aq-enter">
      <PageHeader
        crumbs={[
          { href: "/", label: "首页" },
          { href: "/strategies", label: "策略实验室" },
        ]}
        title={
          editingName ? (
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                rename.mutate();
              }}
            >
              <Input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-10 w-[280px] text-[20px] font-semibold"
                onBlur={() => {
                  if (name.trim() && name !== strategy.name) rename.mutate();
                  else setEditingName(false);
                }}
              />
            </form>
          ) : (
            <button
              type="button"
              className="cursor-text rounded-lg text-left hover:bg-aq-secondary"
              onClick={() => setEditingName(true)}
              title="点击重命名"
            >
              {strategy.name}
            </button>
          )
        }
        description={strategy.description || "结构化策略工作区。代码是信号的唯一来源。"}
        action={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Badge tone="neutral">{labelStatus(strategy.status)}</Badge>
            <Badge tone="blue">v{strategy.latest_version?.version ?? 1}</Badge>
            {dirty ? <Badge tone="amber">未保存</Badge> : null}
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
              删除
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-aq border border-aq-border bg-aq-bg px-3 py-2.5 shadow-aq">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-[11px] text-aq-muted">
            开始
            <Input type="date" className="w-[138px]" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label className="flex items-center gap-1.5 text-[11px] text-aq-muted">
            结束
            <Input type="date" className="w-[138px]" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
          <label className="flex items-center gap-1.5 text-[11px] text-aq-muted">
            本金
            <Input
              type="number"
              min={1000}
              step={1000}
              className="w-28"
              value={capital}
              onChange={(e) => setCapital(e.target.value)}
            />
          </label>
          <label className="flex items-center gap-1.5 text-[11px] text-aq-muted">
            标的池
            <select
              className="h-9 rounded-lg border border-aq-border bg-aq-bg px-2 text-sm text-aq-text outline-none focus:border-aq-primary/40"
              value={universeId}
              onChange={(e) => setUniverseId(e.target.value)}
            >
              <option value="">快照全部标的</option>
              {(universes.data || []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                  {item.member_count ? `（${item.member_count}）` : ""}
                </option>
              ))}
            </select>
          </label>
          <Input
            className="w-44"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="版本说明"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={() => setConfirmRestore(true)}>
            恢复模板代码
          </Button>
          <Button variant="secondary" onClick={() => save.mutate()} disabled={save.isPending || !dirty}>
            {save.isPending ? "保存中…" : "保存版本"}
          </Button>
          <Button onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? "提交中…" : "运行回测"}
          </Button>
        </div>
      </div>

      {trialStats.data && trialStats.data.total_trials > 0 ? (
        <p className="text-xs text-aq-muted">
          已在此策略族上试验 {trialStats.data.total_trials} 次
          {trialStats.data.by_snapshot[0]
            ? `（当前快照 ${trialStats.data.by_snapshot[0].snapshot_key || "—"}：${trialStats.data.by_snapshot[0].count} 次）`
            : ""}
          。多次试验会抬高过拟合风险。
        </p>
      ) : null}

      {code.includes("AfterMarketClose") ? (
        <p className="text-xs text-aq-negative">
          当前代码使用了已失效的 AfterMarketClose。请点击「恢复模板代码」，否则回测会失败。
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-12 gap-4">
        <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-3">
          <div className="border-b border-aq-border px-4 py-3 text-sm font-medium">策略构建器</div>
          <BuilderPanel config={config} onChange={setConfig} />
        </Card>

        <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-6">
          <div className="flex items-center justify-between border-b border-aq-border px-4 py-3">
            <div className="text-sm font-medium">strategy.py</div>
            <span className="text-[11px] text-aq-muted">Python · Monaco · ⌘S 保存</span>
          </div>
          <div className="min-h-0 flex-1">
            <Editor
              height="100%"
              defaultLanguage="python"
              theme="vs"
              value={code}
              onChange={(v) => setCode(v || "")}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                fontFamily: "SF Mono, Menlo, Monaco, Consolas, monospace",
                scrollBeyondLastLine: false,
                automaticLayout: true,
                padding: { top: 12 },
              }}
            />
          </div>
        </Card>

        <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-3">
          <div className="border-b border-aq-border px-4 py-3 text-sm font-medium">版本历史</div>
          <VersionHistory
            versions={versions.data || []}
            currentId={strategy.latest_version?.id}
            onSelect={(v) => {
              setCode(v.code);
              setConfig(v.config || {});
              setMessage(`恢复 v${v.version}`);
              toast(`已载入 v${v.version}`, "info");
            }}
          />
        </Card>
      </div>

      <ConfirmDialog
        open={confirmRestore}
        title="恢复模板代码？"
        description="会覆盖编辑器中的当前代码。未保存的修改将丢失，除非你先保存版本。"
        confirmLabel="恢复模板"
        onConfirm={() => {
          setCode(SPY_200DMA_TEMPLATE);
          setMessage("恢复 SPY 200 日均线模板");
          toast("已载入最新模板", "info");
        }}
        onClose={() => setConfirmRestore(false)}
      />
      <ConfirmDialog
        open={confirmDelete}
        title="删除这条策略？"
        description="删除后无法从界面恢复。相关回测记录仍会保留。"
        confirmLabel="删除策略"
        danger
        onConfirm={() => remove.mutate()}
        onClose={() => setConfirmDelete(false)}
      />
    </div>
  );
}
