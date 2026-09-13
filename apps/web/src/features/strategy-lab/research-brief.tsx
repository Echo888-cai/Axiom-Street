import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { Strategy } from "@/lib/api";

const STEPS = [
  {
    number: "01",
    label: "定义假设",
    detail: "明确规则与研究边界",
    href: "/reports",
  },
  {
    number: "02",
    label: "检验历史",
    detail: "记录每一次真实试验",
    href: "/backtests",
  },
  {
    number: "03",
    label: "挑战结论",
    detail: "用独立验证寻找反证",
    href: "/validation",
  },
];

export function ResearchBrief({
  strategies,
  unavailable,
}: {
  strategies: Strategy[];
  unavailable: boolean;
}) {
  const stats = [
    { label: "全部研究", count: strategies.length },
    {
      label: "构思中",
      count: strategies.filter((s) => s.status === "DRAFT").length,
    },
    {
      label: "已回测",
      count: strategies.filter((s) => s.status === "BACKTESTED").length,
    },
    {
      label: "已验证",
      count: strategies.filter((s) => s.status === "VALIDATED").length,
    },
  ];
  return (
    <section aria-label="研究路径与概况" className="as-research-brief">
      <div className="grid gap-8 px-6 py-9 sm:px-10 sm:py-10 xl:grid-cols-[1fr_1.1fr] xl:items-center xl:gap-10">
        <div>
          <p className="as-eyebrow">IDEA · EXPERIMENT · EVIDENCE</p>
          <h2 className="mt-3 text-[25px] font-semibold leading-relaxed tracking-tight sm:text-[34px]">
            把一个想法，<span className="as-brief-accent">研究透。</span>
          </h2>
          <p className="as-brief-muted mt-2 text-xs leading-6">
            从假设出发，让证据说话。
          </p>
        </div>
        <dl className="grid grid-cols-4 gap-3 border-t border-as-primary/10 pt-5 xl:border-l xl:border-t-0 xl:pl-8 xl:pt-0">
          {stats.map((stat) => (
            <div key={stat.label}>
              <dt className="as-brief-muted text-[11px]">{stat.label}</dt>
              <dd className="mt-3 text-[28px] tabular tracking-tight sm:text-[34px]">
                {unavailable ? "—" : String(stat.count).padStart(2, "0")}
              </dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="grid grid-cols-3 border-t border-as-primary/10">
        {STEPS.map((step) => (
          <Link
            key={step.number}
            href={step.href}
            className="group flex min-h-[64px] items-center gap-2 border-r border-as-primary/10 px-3 py-4 last:border-r-0 hover:bg-white/80 sm:min-h-[76px] sm:gap-3 sm:px-10"
          >
            <span className="as-brief-accent text-[11px] tabular">
              {step.number}
            </span>
            <div className="flex-1">
              <span className="text-xs font-medium">{step.label}</span>
              <p className="as-brief-muted mt-1 hidden text-[11px] sm:block">{step.detail}</p>
            </div>
            <ArrowUpRight
              className="as-brief-muted hidden h-3.5 w-3.5 shrink-0 sm:block"
              aria-hidden="true"
            />
          </Link>
        ))}
      </div>
    </section>
  );
}
