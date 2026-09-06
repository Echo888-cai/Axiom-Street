"use client";

import type { OnMount } from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Card } from "@/components/ui/card";
import { toast } from "@/components/ui/toast";
import { SPY_200DMA_TEMPLATE } from "@/lib/spy-200dma";
import { EQUAL_WEIGHT_CONFIG, EQUAL_WEIGHT_TEMPLATE } from "@/lib/equal-weight";
import { BuilderPanel } from "./builder-panel";
import { RunToolbar } from "./run-toolbar";
import { StrategyLabHeader } from "./strategy-lab-header";
import { RunDock } from "./run-dock";
import { EditorPane, type VersionPair } from "./editor-pane";
import { VersionHistoryCard } from "./version-history-card";
import { LabBanners } from "./lab-banners";
import { StrategyDialogs, type RestoreKind } from "./strategy-dialogs";
import { registerPythonLanguageFeatures, applyEngineError } from "./python-lsp";

function friendlyError(message: string): string {
  if (message.includes("Docker is required") || message.includes("Docker")) {
    return "需要 Docker（Colima）才能跑 LEAN 回测。请先执行 colima start，并确认 worker 容器在运行。";
  }
  if (message.includes("AfterMarketClose")) {
    return "当前策略代码使用了已失效的 LEAN API。请点击「恢复 SPY 200DMA」后再运行回测。";
  }
  return message;
}

export function StrategyLab({ strategyId }: { strategyId: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const {
    data: strategy,
    isLoading,
    error,
    refetch,
  } = useQuery({
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
  const [confirmRestore, setConfirmRestore] = useState<RestoreKind>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [pane, setPane] = useState<"code" | "diff">("code");
  const [runId, setRunId] = useState<string | null>(null);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const lspRef = useRef<{ dispose: () => void } | null>(null);

  useEffect(() => {
    return () => lspRef.current?.dispose();
  }, []);

  useEffect(() => {
    if (strategy?.latest_version?.code) setCode(strategy.latest_version.code);
    if (strategy?.latest_version?.config)
      setConfig(strategy.latest_version.config);
    if (strategy?.name) setName(strategy.name);
  }, [
    strategy?.latest_version?.id,
    strategy?.latest_version?.code,
    strategy?.latest_version?.config,
    strategy?.name,
  ]);

  const dirty = useMemo(() => {
    const latest = strategy?.latest_version;
    if (!latest) return Boolean(code);
    return (
      code !== latest.code ||
      JSON.stringify(config) !== JSON.stringify(latest.config)
    );
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

  const comparePair: VersionPair | null = useMemo(() => {
    if (compareIds.length !== 2) return null;
    const left = (versions.data || []).find((v) => v.id === compareIds[0]);
    const right = (versions.data || []).find((v) => v.id === compareIds[1]);
    return left && right ? { left, right } : null;
  }, [compareIds, versions.data]);

  useEffect(() => {
    if (compareIds.length === 2) setPane("diff");
  }, [compareIds]);

  function applyMarkers(result: {
    ok: boolean;
    message: string | null;
    line: number | null;
    column: number | null;
  }) {
    const editor = editorRef.current;
    const monacoApi = monacoRef.current;
    const model = editor?.getModel();
    if (!editor || !monacoApi || !model) return;
    monacoApi.editor.setModelMarkers(
      model,
      "axiom-syntax",
      result.ok
        ? []
        : [
            {
              startLineNumber: result.line || 1,
              startColumn: result.column || 1,
              endLineNumber: result.line || 1,
              endColumn: (result.column || 1) + 12,
              message: result.message || "语法错误",
              severity: monacoApi.MarkerSeverity.Error,
            },
          ],
    );
  }

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

  const run = useMutation({
    mutationFn: async () => {
      const lint = await api.checkSyntax(code);
      applyMarkers(lint);
      if (!lint.ok) {
        throw new Error(
          `语法错误：第 ${lint.line} 行 ${lint.message || ""}`.trim(),
        );
      }
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
      if (bt.cache_hit) {
        toast("命中结果缓存，未重复计入试验台账", "ok");
      } else {
        toast("回测已提交，留在实验室继续改", "ok");
      }
      setRunId(bt.id);
      qc.invalidateQueries({ queryKey: ["backtests"] });
      qc.invalidateQueries({ queryKey: ["trial-stats", strategyId] });
    },
    onError: (err: Error) => toast(friendlyError(err.message), "err"),
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty) save.mutate();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (!run.isPending) run.mutate();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dirty, save, run]);

  if (error)
    return (
      <Card>
        <EmptyState
          title="无法读取这项研究"
          description={error.message}
          action={
            <Button variant="secondary" onClick={() => refetch()}>
              重新读取
            </Button>
          }
        />
      </Card>
    );

  if (isLoading || !strategy) {
    return <Card className="h-[70vh] animate-pulse bg-as-secondary" />;
  }

  return (
    <div className="flex min-h-[calc(100vh-12rem)] flex-col gap-4 as-enter">
      <StrategyLabHeader
        strategy={strategy}
        strategyId={strategyId}
        editingName={editingName}
        name={name}
        dirty={dirty}
        onNameChange={setName}
        onStartEdit={() => setEditingName(true)}
        onCommitName={() => {
          if (name.trim() && name !== strategy.name) rename.mutate();
          else setEditingName(false);
        }}
        onBlurName={() => {
          if (name.trim() && name !== strategy.name) rename.mutate();
          else setEditingName(false);
        }}
        onDelete={() => setConfirmDelete(true)}
      />

      <RunToolbar
        startDate={startDate}
        endDate={endDate}
        capital={capital}
        universeId={universeId}
        message={message}
        universes={universes.data || []}
        onStartDate={setStartDate}
        onEndDate={setEndDate}
        onCapital={setCapital}
        onUniverseId={setUniverseId}
        onMessage={setMessage}
        dirty={dirty}
        savePending={save.isPending}
        onSave={() => save.mutate()}
        runPending={run.isPending}
        onRun={() => run.mutate()}
        onRestore={(kind) => setConfirmRestore(kind)}
      />

      {runId ? (
        <RunDock
          backtestId={runId}
          onDismiss={() => setRunId(null)}
          onFailure={(error) => {
            const monacoApi = monacoRef.current;
            const editor = editorRef.current;
            if (monacoApi && editor) applyEngineError(monacoApi, editor, error);
          }}
        />
      ) : null}

      <LabBanners
        trials={trialStats.data}
        legacyCode={code.includes("AfterMarketClose")}
      />

      <div className="grid min-h-[520px] flex-1 grid-cols-12 gap-4">
        <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-3">
          <div className="border-b border-as-border px-4 py-3 text-sm font-medium">
            策略构建器
          </div>
          <BuilderPanel config={config} onChange={setConfig} />
        </Card>

        <EditorPane
          code={code}
          onChange={setCode}
          comparePair={comparePair}
          pane={pane}
          onPaneChange={setPane}
          onMountEditor={(editor, monacoApi) => {
            editorRef.current = editor;
            monacoRef.current = monacoApi;
            lspRef.current?.dispose();
            lspRef.current = registerPythonLanguageFeatures(monacoApi);
          }}
        />

        <VersionHistoryCard
          versions={versions.data || []}
          currentId={strategy.latest_version?.id}
          compareIds={compareIds}
          onToggleCompare={(id) =>
            setCompareIds((ids) => {
              if (ids.includes(id)) return ids.filter((x) => x !== id);
              if (ids.length >= 2) return [ids[1], id];
              return [...ids, id];
            })
          }
          onSelect={(v) => {
            setCode(v.code);
            setConfig(v.config || {});
            setMessage(`恢复 v${v.version}`);
            setPane("code");
            toast(`已载入 v${v.version}`, "info");
          }}
        />
      </div>

      <StrategyDialogs
        restore={confirmRestore}
        deleteOpen={confirmDelete}
        onCloseRestore={() => setConfirmRestore(null)}
        onConfirmRestore={(kind) => {
          if (kind === "equal") {
            setCode(EQUAL_WEIGHT_TEMPLATE);
            setConfig(EQUAL_WEIGHT_CONFIG);
            setMessage("加载等权横截面模板");
            toast("已载入等权 1/N 模板", "info");
          } else {
            setCode(SPY_200DMA_TEMPLATE);
            setMessage("恢复 SPY 200 日均线模板");
            toast("已载入最新模板", "info");
          }
        }}
        onCloseDelete={() => setConfirmDelete(false)}
        onConfirmDelete={() => remove.mutate()}
      />
    </div>
  );
}
