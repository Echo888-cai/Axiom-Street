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
import { useT } from "@/lib/i18n";

import { EQUAL_WEIGHT_CONFIG, EQUAL_WEIGHT_TEMPLATE } from "@/lib/equal-weight";
import { BuilderPanel } from "./builder-panel";
import { GuidedBuilder } from "./guided-builder";
import { compileTrend, validateExperiment } from "./guided-strategy";
import { Code2, LayoutTemplate, FlaskConical } from "lucide-react";
import { RunToolbar } from "./run-toolbar";
import { StrategyLabHeader } from "./strategy-lab-header";
import { RunDock } from "./run-dock";
import { EditorPane, type VersionPair } from "./editor-pane";
import { VersionHistoryCard } from "./version-history-card";
import { LabBanners } from "./lab-banners";
import { StrategyDialogs, type RestoreKind } from "./strategy-dialogs";
import { registerPythonLanguageFeatures, applyEngineError } from "./python-lsp";

function fmt(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) =>
    String(vars[key] ?? ""),
  );
}

function friendlyError(
  message: string,
  t: (key: string) => string,
): string {
  if (message.includes("Docker is required") || message.includes("Docker")) {
    return t("strategy.dockerRequired");
  }
  if (message.includes("AfterMarketClose")) {
    return t("strategy.deprecatedLeanApi");
  }
  return message;
}

export function StrategyLab({ strategyId }: { strategyId: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const t = useT();
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

  const [mode, setMode] = useState<"guided" | "professional">("guided");
  const [rulesPending, setRulesPending] = useState(false);
  const [builderRevision, setBuilderRevision] = useState(0);
  const [code, setCode] = useState("");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState(t("strategy.defaultCommitMessage"));
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
      if (!dirty && !rulesPending) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBefore);
    return () => window.removeEventListener("beforeunload", onBefore);
  }, [dirty, rulesPending]);

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
              message: result.message || t("strategy.syntaxMarker"),
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
      toast(t("strategy.versionSavedToast"), "ok");
    },
    onError: (err: Error) => toast(friendlyError(err.message, t), "err"),
  });

  const rename = useMutation({
    mutationFn: () => api.updateStrategy(strategyId, { name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["strategy", strategyId] });
      qc.invalidateQueries({ queryKey: ["strategies"] });
      setEditingName(false);
      toast(t("strategy.nameUpdatedToast"), "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteStrategy(strategyId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["strategies"] });
      toast(t("strategy.strategyDeletedToast"), "info");
      router.push("/strategies");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const run = useMutation({
    mutationFn: async () => {
      if (rulesPending) throw new Error("请先应用规则到代码，或撤销规则草稿。");
      if (!validateExperiment(startDate, endDate, capital)) throw new Error("请检查实验设置：结束日期应晚于开始日期，本金至少为 1,000。");
      const lint = await api.checkSyntax(code);
      applyMarkers(lint);
      if (!lint.ok) {
        const base = fmt(t("strategy.syntaxErrorLine"), {
          line: lint.line as number,
        });
        throw new Error(lint.message ? `${base} ${lint.message}` : base);
      }
      let versionId = strategy?.latest_version?.id;
      if (!versionId || dirty) {
        const version = await api.createVersion(strategyId, {
          code,
          config,
          commit_message: message || t("strategy.saveBeforeRun"),
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
        initial_capital: Number(capital),
        ...(universeId ? { universe_id: universeId } : {}),
      });
    },
    onSuccess: (bt) => {
      if (bt.cache_hit) {
        toast(t("strategy.cacheHitToast"), "ok");
      } else {
        toast(t("strategy.backtestSubmittedToast"), "ok");
      }
      setRunId(bt.id);
      qc.invalidateQueries({ queryKey: ["backtests"] });
      qc.invalidateQueries({ queryKey: ["trial-stats", strategyId] });
    },
    onError: (err: Error) => toast(friendlyError(err.message, t), "err"),
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty && !rulesPending && !save.isPending) save.mutate();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (!run.isPending && !save.isPending) run.mutate();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dirty, rulesPending, save, run]);

  if (error)
    return (
      <Card>
        <EmptyState
          title={t("strategy.labLoadErrorTitle")}
          description={error.message}
          action={
            <Button variant="secondary" onClick={() => refetch()}>
              {t("strategy.retryLoad")}
            </Button>
          }
        />
      </Card>
    );

  if (isLoading || !strategy) {
    return <Card className="h-[70vh] animate-pulse bg-as-secondary" />;
  }

  const experiment = (<RunToolbar
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
        blocked={rulesPending}
        professional={mode === "professional"}
        onRun={() => run.mutate()}
        onRestore={(kind) => setConfirmRestore(kind)}
      />);

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

      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-as-border pb-4">
        <ol className="flex flex-wrap items-center gap-5 text-sm" aria-label="研究流程">
          <li className="rounded-lg bg-as-primary/10 px-3 py-2 font-medium text-as-primary">01 构建规则</li><li className="text-as-muted">02 运行实验</li><li className="text-as-muted">03 检验结果</li>
        </ol>
        <div className="flex rounded-xl border border-as-border bg-as-bg p-1" aria-label="编辑模式">
          <Button variant={mode === "guided" ? "secondary" : "ghost"} aria-pressed={mode === "guided"} onClick={() => setMode("guided")}><LayoutTemplate className="h-4 w-4" />规则构建</Button>
          <Button variant={mode === "professional" ? "secondary" : "ghost"} aria-pressed={mode === "professional"} onClick={() => setMode("professional")}><Code2 className="h-4 w-4" />专业模式</Button>
        </div>
      </div>
      {rulesPending && <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-as-primary/20 bg-as-primary/5 p-4 text-sm">规则草稿尚未应用，运行实验已暂停。<Button variant="secondary" onClick={() => { setBuilderRevision((v) => v + 1); setRulesPending(false); }}>撤销规则草稿</Button></div>}
      <div className={mode === "guided" ? "grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_340px]" : "hidden"}>
        <GuidedBuilder key={`${strategy.latest_version?.id}-${builderRevision}`} config={config} code={code} onPending={setRulesPending} onApply={(result) => { setCode(result.code); setConfig(result.config); setMessage("应用均线趋势规则"); }} />
        <aside className="space-y-4 xl:sticky xl:top-24">
          {experiment}
          <details className="rounded-as border border-as-border bg-as-bg p-5"><summary className="flex cursor-pointer items-center gap-2 text-sm font-medium"><FlaskConical className="h-4 w-4 text-as-primary" aria-hidden="true" />如何判断实验有没有价值？</summary><div className="mt-4 space-y-3 text-sm leading-7 text-as-muted"><p>一次只修改一个规则。收益更高，不一定说明策略更可靠。</p><ul className="space-y-2"><li>是否跑赢同一时期的基准？</li><li>最差时亏损多少，持续多久？</li><li>扣除成本后，优势还在吗？</li></ul><p>自由描述暂不生成代码；研究助手用于解释证据。自定义策略、等权模板与版本对比请进入专业模式。</p></div></details>
        </aside>
      </div>

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

      <div className={mode === "professional" ? "grid min-h-[520px] flex-1 grid-cols-12 gap-4" : "hidden"}>
        <details className="col-span-12 rounded-as border border-as-border bg-as-bg p-4">
          <summary className="cursor-pointer text-sm font-medium">研究配置与备注</summary>
          <p className="px-4 pt-4 text-xs leading-relaxed text-as-muted">专业模式：配置用于研究记录，交易行为以代码为准。要同步生成代码，请使用规则构建。</p>
          <BuilderPanel config={config} onChange={setConfig} />
        </details>

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
            setRulesPending(false);
            setBuilderRevision((r) => r + 1);
            setCode(v.code);
            setConfig(v.config || {});
            setMessage(
              fmt(t("strategy.restoredVersionMessage"), { version: v.version }),
            );
            setPane("code");
            toast(
              fmt(t("strategy.versionLoadedToast"), { version: v.version }),
              "info",
            );
          }}
        />
      </div>

      {mode === "professional" && experiment}


      <StrategyDialogs
        restore={confirmRestore}
        deleteOpen={confirmDelete}
        onCloseRestore={() => setConfirmRestore(null)}
        onConfirmRestore={(kind) => {
          setRulesPending(false);
          setBuilderRevision((r) => r + 1);
          if (kind === "equal") {
            setCode(EQUAL_WEIGHT_TEMPLATE);
            setConfig(EQUAL_WEIGHT_CONFIG);
            setMessage(t("strategy.equalRestoreMessage"));
            toast(t("strategy.equalTemplateLoadedToast"), "info");
          } else {
            const restored = compileTrend({ symbol: "SPY", lookback: 200, position: 100, slippage: 5, hypothesis: "SPY 站上长期均线持有，跌破转为现金。" });
            setCode(restored.code);
            setConfig(restored.config);
            setMessage(t("strategy.spyRestoreMessage"));
            toast(t("strategy.latestTemplateLoadedToast"), "info");
          }
        }}
        onCloseDelete={() => setConfirmDelete(false)}
        onConfirmDelete={() => remove.mutate()}
      />
    </div>
  );
}
