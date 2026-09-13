"use client";

import type { OnMount } from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { toast } from "@/components/ui/toast";
import { useT } from "@/lib/i18n";
import { formatTemplate } from "@/lib/utils";
import { validateExperiment } from "./guided-strategy";
import type { VersionPair } from "./editor-pane";
import type { RestoreKind } from "./strategy-dialogs";

function friendlyError(message: string, t: (key: string) => string): string {
  if (message.includes("Docker is required") || message.includes("Docker")) {
    return t("strategy.dockerRequired");
  }
  if (message.includes("AfterMarketClose")) {
    return t("strategy.deprecatedLeanApi");
  }
  return message;
}

export function useStrategyLab(strategyId: string) {
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
        const base = formatTemplate(t("strategy.syntaxErrorLine"), {
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

  return {
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
  };
}
