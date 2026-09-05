import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

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
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
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
        <h1 className="text-[28px] sm:text-[32px] font-semibold tracking-[-0.045em] text-as-text">
          {title}
        </h1>
        {description ? (
          <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-as-muted">
            {description}
          </p>
        ) : null}
      </div>
      {action ? (
        <div className="flex flex-wrap items-center gap-2">{action}</div>
      ) : null}
    </div>
  );
}
