"use client";

import { useState } from "react";
import { Tabs } from "@/components/ui/tabs";
import { Disclosure } from "@/components/ui/disclosure";
import { useT } from "@/lib/i18n";

type Chapter = "hypothesis" | "method" | "conclusion" | "failure_modes";
const chapters: { id: Chapter; label: string; prompt: string }[] = [
  { id: "hypothesis", label: "研究假设", prompt: "为什么这个交易想法可能有效？" },
  { id: "method", label: "检验方法", prompt: "记录实际完成的回测与验证。" },
  { id: "conclusion", label: "研究结论", prompt: "数据支持了什么，又否定了什么？" },
  { id: "failure_modes", label: "失效条件", prompt: "什么情况下，这个策略可能失效？" },
];

export function NoteFields({ draft, onChange }: {
  draft: Partial<Record<Chapter, string>>;
  onChange: (key: Chapter, value: string) => void;
}) {
  const t = useT();
  const [active, setActive] = useState<Chapter>("hypothesis");
  const chapter = chapters.find((item) => item.id === active)!;
  return <div className="flex min-h-0 flex-1 flex-col gap-5 p-5 sm:p-6">
    <Tabs value={active} onChange={(id) => setActive(id as Chapter)} items={chapters} />
    <label className="flex min-h-0 flex-1 flex-col gap-3">
      <span className="sr-only">{chapter.label}</span>
      <textarea value={draft[active] ?? ""} onChange={(e) => onChange(active, e.target.value)} placeholder={chapter.prompt} className="as-note-editor min-h-[280px] w-full flex-1 resize-y rounded-2xl border border-as-border/60 bg-as-secondary/25 p-5 text-sm leading-8 outline-none focus-visible:ring-2 focus-visible:ring-as-primary/30" />
    </label>
    <Disclosure title="写作提示">{t(`common.research.sections.${active}.hint`)}</Disclosure>
  </div>;
}
