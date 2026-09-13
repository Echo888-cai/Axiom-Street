"use client";

import { Code2, FlaskConical, LayoutTemplate } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LabModeBar({
  mode,
  onMode,
  rulesPending,
  onDiscardRules,
}: {
  mode: "guided" | "professional";
  onMode: (mode: "guided" | "professional") => void;
  rulesPending: boolean;
  onDiscardRules: () => void;
}) {
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-as-border pb-4">
        <ol className="flex flex-wrap items-center gap-5 text-sm" aria-label="研究流程">
          <li className="rounded-lg bg-as-primary/10 px-3 py-2 font-medium text-as-primary">01 构建规则</li><li className="text-as-muted">02 运行实验</li><li className="text-as-muted">03 检验结果</li>
        </ol>
        <div className="flex rounded-xl border border-as-border bg-as-bg p-1" aria-label="编辑模式">
          <Button variant={mode === "guided" ? "secondary" : "ghost"} aria-pressed={mode === "guided"} onClick={() => onMode("guided")}><LayoutTemplate className="h-4 w-4" />规则构建</Button>
          <Button variant={mode === "professional" ? "secondary" : "ghost"} aria-pressed={mode === "professional"} onClick={() => onMode("professional")}><Code2 className="h-4 w-4" />专业模式</Button>
        </div>
      </div>
      {rulesPending && <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-as-primary/20 bg-as-primary/5 p-4 text-sm">规则草稿尚未应用，运行实验已暂停。<Button variant="secondary" onClick={onDiscardRules}>撤销规则草稿</Button></div>}
    </>
  );
}

export function GuidedWorkspace({
  active,
  experiment,
  children,
}: {
  active: boolean;
  experiment: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className={active ? "grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_340px]" : "hidden"}>
      {children}
      <aside className="space-y-4 xl:sticky xl:top-24">
        {experiment}
        <details className="rounded-as border border-as-border bg-as-bg p-5"><summary className="flex cursor-pointer items-center gap-2 text-sm font-medium"><FlaskConical className="h-4 w-4 text-as-primary" aria-hidden="true" />如何判断实验有没有价值？</summary><div className="mt-4 space-y-3 text-sm leading-7 text-as-muted"><p>一次只修改一个规则。收益更高，不一定说明策略更可靠。</p><ul className="space-y-2"><li>是否跑赢同一时期的基准？</li><li>最差时亏损多少，持续多久？</li><li>扣除成本后，优势还在吗？</li></ul><p>自由描述暂不生成代码；研究助手用于解释证据。自定义策略、等权模板与版本对比请进入专业模式。</p></div></details>
      </aside>
    </div>
  );
}
