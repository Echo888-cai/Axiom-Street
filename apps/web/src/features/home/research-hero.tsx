import Link from "next/link";
import { ArrowUpRight, Plus, ArrowRight } from "lucide-react";
import { AxiomMark } from "@/components/brand/axiom-mark";

export function ResearchHero() {
  return (
    <section className="relative isolate overflow-hidden rounded-[24px] border border-white bg-gradient-to-br from-white via-white to-[#edf1f6] px-6 py-8 shadow-as sm:px-8 lg:py-9">
      <div className="relative z-10 max-w-full sm:max-w-[65%]">
        <div className="as-eyebrow flex items-center gap-2.5">
          <span className="h-px w-5 bg-as-muted/50" /> WHERE IDEAS BECOME
          EVIDENCE
        </div>
        <h2 className="mt-5 text-[26px] font-medium leading-[1.45] tracking-[-.045em] sm:text-[32px]">
          让每一份直觉，
          <br />
          <span className="text-as-muted">都有据可循。</span>
        </h2>
        <p className="mt-3 max-w-sm text-xs leading-6 text-as-muted">
          一个安静的空间，连接假设、数据与发现。
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/strategies"
            className="as-button-primary inline-flex min-h-10 items-center gap-2 rounded-xl px-4 text-xs font-medium text-white"
          >
            <Plus className="h-3.5 w-3.5" /> 开始一项研究
          </Link>
          <Link
            href="/reports"
            className="inline-flex min-h-10 items-center gap-1.5 rounded-xl px-2 text-xs text-as-muted hover:text-as-text"
          >
            研究笔记 <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute hidden sm:block -right-20 top-1/2 h-[350px] w-[350px] -translate-y-1/2 opacity-55 sm:right-0 sm:opacity-100 xl:right-12"
      >
        <div className="absolute inset-2 rounded-full border border-slate-300/15" />
        <div className="absolute inset-9 rounded-full border border-slate-300/25" />
        <div className="absolute inset-[68px] rounded-full border border-white/80 bg-white/20 shadow-[inset_0_1px_2px_white,0_8px_24px_rgba(70,90,120,.025)]" />
        <div className="absolute left-1/2 top-1/2 h-[148px] w-[148px] -translate-x-1/2 -translate-y-1/2 rotate-[-13deg] rounded-[38px] border border-white bg-gradient-to-br from-white/95 to-[#e3e9f1]/75 shadow-[inset_0_2px_2px_white,0_24px_45px_-18px_rgba(70,90,120,.23)] backdrop-blur-xl" />
        <div className="absolute left-1/2 top-1/2 flex h-[148px] w-[148px] -translate-x-1/2 -translate-y-1/2 rotate-[8deg] items-center justify-center rounded-[38px] border border-white/90 bg-gradient-to-br from-white/75 to-[#f0f3f8]/65 shadow-[inset_0_2px_1px_white,0_10px_30px_-10px_rgba(70,90,120,.13)] backdrop-blur-sm">
          <AxiomMark className="h-[76px] w-[76px] text-[#7f8ea3]" />
        </div>
        <span className="absolute left-12 top-[96px] h-2 w-2 rounded-full border border-white bg-[#cad4e2] shadow-sm" />
        <span className="absolute bottom-[75px] right-[71px] h-1.5 w-1.5 rounded-full bg-[#b3c0d2]" />
        <span className="absolute bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap text-[8px] tracking-[.28em] text-[#8a96a7]">
          HYPOTHESIS <ArrowRight className="mx-1 inline h-2.5 w-2.5" /> EVIDENCE
        </span>
      </div>
    </section>
  );
}
