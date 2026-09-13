"use client";

import Editor from "@monaco-editor/react";
import { Card } from "@/components/ui/card";
import { Tabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n";
import type { StrategyVersion } from "@/lib/api";
import { VersionDiff } from "./version-diff";

export type VersionPair = {
  left: StrategyVersion;
  right: StrategyVersion;
};

export function EditorPane({
  code,
  onChange,
  comparePair,
  pane,
  onPaneChange,
  onMountEditor,
}: {
  code: string;
  onChange: (code: string) => void;
  comparePair?: VersionPair | null;
  pane: "code" | "diff";
  onPaneChange: (pane: "code" | "diff") => void;
  onMountEditor: NonNullable<Parameters<typeof Editor>[0]["onMount"]>;
}) {
  const t = useT();
  return (
    <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-9">
      <div className="flex items-center justify-between border-b border-as-border px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="text-sm font-medium">strategy.py</div>
          {comparePair ? (
            <Tabs
              value={pane}
              onChange={(id) => onPaneChange(id as "code" | "diff")}
              items={[
                { id: "code", label: t("strategy.editorTabCode") },
                { id: "diff", label: t("strategy.editorTabDiff") },
              ]}
            />
          ) : null}
        </div>
        <span className="hidden text-[11px] text-as-muted xl:block">
          {t("strategy.editorShortcuts")}
        </span>
      </div>
      {pane === "diff" && comparePair ? (
        <VersionDiff left={comparePair.left} right={comparePair.right} />
      ) : (
        <div className="h-[600px] min-h-[420px] flex-1">
          <Editor
            height="100%"
            defaultLanguage="python"
            theme="vs"
            value={code}
            onMount={onMountEditor}
            onChange={(v) => onChange(v || "")}
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
      )}
    </Card>
  );
}
