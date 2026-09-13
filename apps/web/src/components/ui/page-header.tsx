import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Disclosure } from "./disclosure";

export function PageHeader({
  title,
  description,
  action,
  crumbs,
}: {
  title: ReactNode;
  description?: string;
  action?: ReactNode;
  crumbs?: { href: string; label: string }[];
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-4">
      <div className="min-w-0 flex-1 basis-64">
        {crumbs?.length ? (
          <nav className="mb-2 flex items-center gap-1 text-xs text-as-muted">
            {crumbs.map((c, i) => (
              <span key={c.href} className="flex items-center gap-1">
                {i > 0 ? <ChevronRight className="h-3 w-3" /> : null}
                <Link
                  href={c.href}
                  className="cursor-pointer hover:text-as-text"
                >
                  {c.label}
                </Link>
              </span>
            ))}
          </nav>
        ) : null}
        <h1 className="text-[28px] leading-tight sm:text-[36px] font-semibold tracking-[-0.045em] text-as-text">
          {title}
        </h1>
        {description ? (
          description.length > 45 ? <Disclosure title="关于此页面" className="mt-3 max-w-xl border-0 bg-transparent [&>summary]:min-h-8 [&>summary]:px-0 [&>summary]:py-1">{description}</Disclosure> : <p className="mt-2 max-w-xl text-[13px] leading-relaxed text-as-muted">{description}</p>
        ) : null}
      </div>
      {action ? (
        <div className="flex max-w-full flex-wrap items-center gap-2">{action}</div>
      ) : null}
    </div>
  );
}
