import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Hourglass } from "lucide-react";

export function PhasePlaceholder({
  title,
  phase,
  description,
  items,
}: {
  title: string;
  phase: string;
  description: string;
  items?: string[];
}) {
  return (
    <div className="space-y-6 aq-enter">
      <PageHeader title={title} description={description} />
      <Card className="overflow-hidden p-0">
        <div className="flex flex-col items-start gap-6 p-8 md:flex-row md:items-center">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[rgba(22,119,255,0.08)] text-aq-primary">
            <Hourglass className="h-5 w-5" strokeWidth={1.75} />
          </span>
          <div>
            <div className="text-[11px] font-medium tracking-wider text-aq-primary">{phase}</div>
            <h2 className="mt-1 text-base font-medium text-aq-text">当前版本尚未开放</h2>
            <p className="mt-1.5 max-w-md text-sm leading-relaxed text-aq-muted">
              现在把回测链路做可信。这个入口会保留，后续阶段直接接入。
            </p>
          </div>
        </div>
        {items?.length ? (
          <ul className="grid gap-px border-t border-aq-border bg-aq-secondary/40 sm:grid-cols-3">
            {items.map((item, i) => (
              <li key={item} className="bg-aq-bg px-6 py-5 text-sm text-aq-muted">
                <span className="mb-2 block text-[11px] text-aq-primary">0{i + 1}</span>
                {item}
              </li>
            ))}
          </ul>
        ) : null}
      </Card>
    </div>
  );
}
