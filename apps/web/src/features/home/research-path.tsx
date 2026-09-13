"use client";

import Link from "next/link";
import {
  ArrowUpRight,
  Check,
  FlaskConical,
  LineChart,
  ShieldCheck,
} from "lucide-react";
import { Card, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export function ResearchPath({
  hasStrategy,
  hasBacktest,
}: {
  hasStrategy: boolean;
  hasBacktest: boolean;
}) {
  const t = useT();
  const steps = [
    {
      label: t("common.path.hypothesis"),
      detail: t("common.path.hypothesisDetail"),
      href: "/strategies",
      icon: FlaskConical,
      done: hasStrategy,
    },
    {
      label: t("common.path.history"),
      detail: t("common.path.historyDetail"),
      href: "/backtests",
      icon: LineChart,
      done: hasBacktest,
    },
    {
      label: t("common.path.robust"),
      detail: t("common.path.robustDetail"),
      href: "/validation",
      icon: ShieldCheck,
      done: false,
    },
  ];
  return (
    <section id="research-path" aria-label="研究操作流程" className="scroll-mt-24"><Card className="h-full flex flex-col">
      <CardHeader
        title={t("common.path.title")}
        hint={
          <p className="mt-1 text-xs text-as-muted">
            {t("common.path.hint")}
          </p>
        }
      />
      <div className="flex-1 space-y-1 pt-1">
        {steps.map((step, i) => (
          <Link
            key={step.href}
            href={step.href}
            className={cn("group relative flex items-start gap-3.5 rounded-xl px-3 py-4 transition-colors hover:bg-as-secondary/80", i === (hasBacktest ? 2 : hasStrategy ? 1 : 0) && "bg-as-primary/5")}
          >
            {i < 2 && (
              <span
                aria-hidden="true"
                className="absolute left-[31px] top-[58px] h-5 border-l border-dashed border-as-border"
              />
            )}
            <span className="as-icon-well h-10 w-10 rounded-[14px]">
              <step.icon className="h-4 w-4" strokeWidth={1.5} />
            </span>
            <span className="flex-1 pt-0.5">
              <span className="block text-sm font-medium">{step.label}{i === (hasBacktest ? 2 : hasStrategy ? 1 : 0) && <span className="ml-2 text-[10px] font-medium text-as-primary">下一步</span>}</span>
              <span className="mt-1.5 block text-xs text-as-muted">
                {step.detail}
              </span>
            </span>
            <span className="pt-1.5 text-as-muted">
              {step.done ? (
                <Check className="h-3.5 w-3.5 text-as-positive" />
              ) : (
                <span className="text-[10px] tabular">0{i + 1}</span>
              )}
            </span>
          </Link>
        ))}
      </div>
      <Link
        href="/validation"
        className="mt-3 flex items-center justify-between border-t border-as-border pt-4 text-xs text-as-muted hover:text-as-primary"
      >
        {t("common.path.process")}
        <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
      </Link>
    </Card></section>
  );
}
