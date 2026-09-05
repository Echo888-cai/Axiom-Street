import Link from "next/link";
import {
  ArrowUpRight,
  Check,
  FlaskConical,
  LineChart,
  ShieldCheck,
} from "lucide-react";
import { Card, CardHeader } from "@/components/ui/card";

export function ResearchPath({
  hasStrategy,
  hasBacktest,
}: {
  hasStrategy: boolean;
  hasBacktest: boolean;
}) {
  const steps = [
    {
      label: "提出一个假设",
      detail: "记录逻辑，构建策略",
      href: "/strategies",
      icon: FlaskConical,
      done: hasStrategy,
    },
    {
      label: "让历史数据回答",
      detail: "冻结数据，复现结果",
      href: "/backtests",
      icon: LineChart,
      done: hasBacktest,
    },
    {
      label: "检验它的稳健性",
      detail: "样本外验证，审视偏差",
      href: "/validation",
      icon: ShieldCheck,
      done: false,
    },
  ];
  return (
    <Card className="flex flex-col">
      <CardHeader
        title="从想法，到证据"
        hint={
          <p className="mt-1 text-[11px] text-as-muted">
            好的研究，有一条清晰的路径。
          </p>
        }
      />
      <div className="flex-1 space-y-1 pt-1">
        {steps.map((step, i) => (
          <Link
            key={step.href}
            href={step.href}
            className="group relative flex items-start gap-3.5 rounded-xl py-4 transition-colors hover:bg-as-secondary/60"
          >
            {i < 2 && (
              <span
                aria-hidden="true"
                className="absolute left-[19px] top-[58px] h-5 border-l border-dashed border-as-border"
              />
            )}
            <span className="as-icon-well h-10 w-10 rounded-xl">
              <step.icon className="h-4 w-4" strokeWidth={1.5} />
            </span>
            <span className="flex-1 pt-0.5">
              <span className="block text-xs font-medium">{step.label}</span>
              <span className="mt-1.5 block text-[11px] text-as-muted">
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
        className="mt-3 flex items-center justify-between border-t border-as-border pt-4 text-[11px] text-as-muted hover:text-as-primary"
      >
        比一个好结果更重要的，是可信的过程。
        <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
      </Link>
    </Card>
  );
}
