"use client";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Card } from "@/components/ui/card";
import { toast } from "@/components/ui/toast";
import { useT } from "@/lib/i18n";
import { formatTemplate } from "@/lib/utils";

import { EQUAL_WEIGHT_CONFIG, EQUAL_WEIGHT_TEMPLATE } from "@/lib/equal-weight";
import { BuilderPanel } from "./builder-panel";
import { GuidedBuilder } from "./guided-builder";
import { compileTrend } from "./guided-strategy";
import { RunToolbar } from "./run-toolbar";
import { StrategyLabHeader } from "./strategy-lab-header";
import { RunDock } from "./run-dock";
import { EditorPane } from "./editor-pane";
import { VersionHistoryCard } from "./version-history-card";
import { LabBanners } from "./lab-banners";
import { GuidedWorkspace, LabModeBar } from "./strategy-lab-flow";
import { StrategyDialogs } from "./strategy-dialogs";
import { registerPythonLanguageFeatures, applyEngineError } from "./python-lsp";
import { useStrategyLab } from "./use-strategy-lab";

export function StrategyLab({ strategyId }: { strategyId: string }) {
  const t = useT();
  const {
    strategy,
    isLoading,
    error,
    refetch,
    versions,
    trialStats,
    universes,
    mode,
    setMode,
    rulesPending,
    setRulesPending,
    builderRevision,
    setBuilderRevision,
    code,
    setCode,
    config,
    setConfig,
    message,
    setMessage,
    startDate,
    setStartDate,
    endDate,
    setEndDate,
    capital,
    setCapital,
    universeId,
    setUniverseId,
    editingName,
    setEditingName,
    name,
    setName,
    confirmRestore,
    setConfirmRestore,
    confirmDelete,
    setConfirmDelete,
    compareIds,
    setCompareIds,
    pane,
    setPane,
    runId,
    setRunId,
    editorRef,
    monacoRef,
    lspRef,
    dirty,
    comparePair,
    save,
    rename,
    remove,
    run,
  } = useStrategyLab(strategyId);

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

      <LabModeBar
        mode={mode}
        onMode={setMode}
        rulesPending={rulesPending}
        onDiscardRules={() => {
          setBuilderRevision((v) => v + 1);
          setRulesPending(false);
        }}
      />

      <GuidedWorkspace active={mode === "guided"} experiment={experiment}>
        <GuidedBuilder key={`${strategy.latest_version?.id}-${builderRevision}`} config={config} code={code} onPending={setRulesPending} onApply={(result) => { setCode(result.code); setConfig(result.config); setMessage("应用均线趋势规则"); }} />
      </GuidedWorkspace>

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
              formatTemplate(t("strategy.restoredVersionMessage"), { version: v.version }),
            );
            setPane("code");
            toast(
              formatTemplate(t("strategy.versionLoadedToast"), { version: v.version }),
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
