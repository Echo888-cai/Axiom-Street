"use client";

import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Hourglass } from "lucide-react";
import { useT } from "@/lib/i18n";
import { Disclosure } from "@/components/ui/disclosure";

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
  const t = useT();
  return (
    <div className="space-y-6 as-enter">
      <PageHeader title={title} description={description} />
      <Card className="overflow-hidden p-0">
        <div className="flex flex-col items-start gap-6 p-8 md:flex-row md:items-center">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[rgba(22,119,255,0.08)] text-as-primary">
            <Hourglass className="h-5 w-5" strokeWidth={1.75} />
          </span>
          <div>
            <div className="text-[11px] font-medium tracking-wider text-as-primary">{phase}</div>
            <h2 className="mt-1 text-base font-medium text-as-text">{t("common.phase.notAvailable")}</h2>
            <p className="mt-1.5 max-w-md text-sm leading-relaxed text-as-muted">
              {t("common.phase.notice")}
            </p>
          </div>
        </div>
        {items?.length ? (
          <Disclosure title="查看规划内容" className="m-5 sm:m-6"><ul className="grid gap-4 sm:grid-cols-3">
            {items.map((item, i) => (
              <li key={item} className="text-sm text-as-muted">
                <span className="mb-2 block text-[11px] text-as-primary">0{i + 1}</span>
                {item}
              </li>
            ))}
          </ul></Disclosure>
        ) : null}
      </Card>
    </div>
  );
}
