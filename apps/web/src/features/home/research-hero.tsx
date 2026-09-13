"use client";

import Link from "next/link";
import { ArrowUpRight, ArrowRight } from "lucide-react";
import { AxiomMark } from "@/components/brand/axiom-mark";
import { useT } from "@/lib/i18n";

export function ResearchHero({ compact = false }: { compact?: boolean }) {
  const t = useT();
  return (
    <section className="as-research-brief flex items-center justify-between gap-8 px-6 py-9 sm:px-10 sm:py-10">
      <div className="relative z-10">
        <p className="as-eyebrow">THE RESEARCH MINDSET</p>
        <h2 className="mt-4 text-[26px] font-semibold leading-snug tracking-tight sm:text-[36px]">
          少一点噪音，<span className="as-brief-accent inline-block">多一点确信。</span>
        </h2>
        <p className="as-brief-muted mt-4 max-w-lg text-sm leading-7">
          {compact
            ? "从假设出发，让证据说话。每一次试验，都让结论更清晰。"
            : t("common.hero.tagline")}
        </p>
        <Link
          href={compact ? "/reports" : "/strategies"}
          className="as-brief-link mt-4 inline-flex min-h-11 items-center gap-2 text-sm font-medium"
        >
          {compact ? "打开研究笔记" : t("common.hero.startResearch")}
          <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>
      <div
        aria-hidden="true"
        className="as-brief-symbol hidden w-48 shrink-0 self-stretch items-center justify-center rounded-3xl lg:flex"
      >
        <div className="text-center">
          <AxiomMark className="mx-auto h-16 w-16 text-as-primary" />
          <p className="as-brief-muted mt-5 text-[9px] tracking-[.16em]">
            HYPOTHESIS <ArrowRight className="mx-1 inline h-3 w-3" /> EVIDENCE
          </p>
        </div>
      </div>
    </section>
  );
}
