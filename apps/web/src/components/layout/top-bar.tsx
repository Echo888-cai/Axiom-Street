"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, Search, Menu, ChevronRight, MessageSquare, Settings2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { BACKTEST_TONE, labelStatus } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { CommandPalette } from "@/components/ui/command-palette";
import { formatRelative } from "@/lib/utils";
import { NAV_ITEMS } from "./nav";
import { useT } from "@/lib/i18n";

export function TopBar({ onMenu, onAssistant }: { onMenu: () => void; onAssistant?: () => void }) {
  const t = useT();
  const pathname = usePathname();
  const current = NAV_ITEMS.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );
  const [searchOpen, setSearchOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const backtests = useQuery({
    queryKey: ["backtests"],
    queryFn: () => api.listBacktests(),
    refetchInterval: 15_000,
  });
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setNotesOpen(false);
        setSearchOpen(true);
      }
      if (event.key === "Escape") setNotesOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const recent = (backtests.data || []).slice(0, 6);
  return (
    <header className="as-glass sticky top-0 z-20 flex h-[68px] shrink-0 items-center justify-between gap-3 border-b border-as-border/60 px-5 sm:px-8 lg:px-10 xl:px-12">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenu}
          aria-label={t("layout.openMenuAria")}
          className="as-action-icon inline-flex md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="hidden text-[11px] text-as-muted sm:block">
          {t("layout.breadcrumbWorkspace")}
        </span>
        <ChevronRight className="hidden h-3 w-3 text-as-muted/50 sm:block" />
        <span className="truncate text-xs font-medium">
          {current ? t(`nav.${current.key}`) : t("layout.researchStudio")}
        </span>
      </div>
      <div className="flex items-center gap-2 sm:gap-4">
        <button
          type="button"
          aria-label={t("layout.searchAria")}
          onClick={() => setSearchOpen(true)}
          className="flex h-11 items-center gap-2.5 rounded-xl border border-as-border/60 bg-as-secondary/60 px-3 text-xs text-as-muted hover:bg-white"
        >
          <Search className="h-4 w-4" strokeWidth={1.6} />
          <span className="hidden lg:block">{t("layout.searchPlaceholder")}</span>
          <kbd className="hidden rounded-md border border-as-border bg-white px-1.5 py-0.5 text-[10px] sm:block">
            ⌘ K
          </kbd>
        </button>
        {onAssistant && <button type="button" onClick={onAssistant} aria-label="打开研究助手" title="研究助手与验证" className="as-button-secondary flex h-11 items-center gap-2 rounded-xl border border-as-border px-3 text-xs font-medium"><MessageSquare className="h-4 w-4" aria-hidden="true" /><span className="hidden sm:inline">研究助手</span></button>}
        <div className="relative">
          <button
            type="button"
            aria-label={t("layout.notesAria")}
            aria-expanded={notesOpen}
            onClick={() => setNotesOpen(!notesOpen)}
            className="as-action-icon relative inline-flex"
          >
            <Bell className="h-4 w-4" strokeWidth={1.6} />
            {recent.some((b) => b.status === "FAILED") && (
              <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-as-negative" />
            )}
          </button>
          {notesOpen && (
            <>
              <button
                type="button"
                aria-label={t("layout.closeNotesAria")}
                onClick={() => setNotesOpen(false)}
                className="fixed inset-0 z-20 cursor-default"
              />
              <section
                aria-label={t("layout.notesSectionAria")}
                className="as-glass absolute -right-10 top-12 z-30 w-80 max-w-[calc(100vw-40px)] overflow-hidden rounded-2xl border border-as-border shadow-as-lg as-scale-in"
              >
                <div className="border-b border-as-border p-4 text-xs font-semibold">
                  {t("layout.recentActivity")}
                </div>
                {backtests.isError ? (
                  <p className="p-6 text-xs leading-relaxed text-as-muted">
                    {t("layout.notesError")}
                  </p>
                ) : backtests.isLoading ? (
                  <p className="p-6 text-xs text-as-muted">{t("layout.notesLoading")}</p>
                ) : !recent.length ? (
                  <p className="p-6 text-xs leading-relaxed text-as-muted">
                    {t("layout.notesEmpty")}
                  </p>                ) : (
                  <ul className="max-h-80 overflow-auto p-2">
                    {recent.map((b) => (
                      <li key={b.id}>
                        <Link
                          href={`/backtests/${b.id}`}
                          onClick={() => setNotesOpen(false)}
                          className="block rounded-xl px-3 py-3 hover:bg-white"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-xs">
                              {b.strategy_name ||
                                `${b.start_date} → ${b.end_date}`}
                            </span>
                            <Badge tone={BACKTEST_TONE[b.status] || "neutral"}>
                              {labelStatus(b.status)}
                            </Badge>
                          </div>
                          <p className="mt-1.5 text-[10px] text-as-muted">
                            {formatRelative(b.finished_at || b.created_at)}
                          </p>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
        <Link
          href="/settings"
          aria-label={t("layout.settingsAria")}
          className="as-action-icon hidden sm:inline-flex"
        >
          <Settings2 className="h-[18px] w-[18px]" aria-hidden="true" />
        </Link>
      </div>
      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
    </header>
  );
}
