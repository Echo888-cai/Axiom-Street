"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, Search, Menu, ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { BACKTEST_TONE, labelStatus } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { CommandPalette } from "@/components/ui/command-palette";
import { formatRelative } from "@/lib/utils";
import { NAV_ITEMS } from "./nav";

export function TopBar({ onMenu }: { onMenu: () => void }) {
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
    <header className="as-glass sticky top-0 z-20 flex h-[72px] shrink-0 items-center justify-between gap-3 border-b border-white/80 px-5 sm:px-8 lg:px-10 xl:px-12">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenu}
          aria-label="打开导航"
          className="flex h-11 w-11 items-center justify-center rounded-xl hover:bg-white md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="hidden text-[11px] text-as-muted sm:block">
          工作空间
        </span>
        <ChevronRight className="hidden h-3 w-3 text-as-muted/50 sm:block" />
        <span className="truncate text-xs font-medium">
          {current?.label || "研究工作室"}
        </span>
      </div>
      <div className="flex items-center gap-2 sm:gap-4">
        <button
          type="button"
          aria-label="搜索策略、回测和页面"
          onClick={() => setSearchOpen(true)}
          className="flex h-11 items-center gap-2.5 rounded-xl px-3 text-xs text-as-muted transition-colors hover:bg-white"
        >
          <Search className="h-4 w-4" strokeWidth={1.6} />
          <span className="hidden lg:block">搜索任何内容…</span>
          <kbd className="hidden rounded-md border border-as-border bg-white px-1.5 py-0.5 text-[10px] sm:block">
            ⌘ K
          </kbd>
        </button>
        <div className="relative">
          <button
            type="button"
            aria-label="最近回测通知"
            aria-expanded={notesOpen}
            onClick={() => setNotesOpen(!notesOpen)}
            className="relative flex h-11 w-11 items-center justify-center rounded-full text-as-muted hover:bg-white"
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
                aria-label="关闭通知"
                onClick={() => setNotesOpen(false)}
                className="fixed inset-0 z-20 cursor-default"
              />
              <section
                aria-label="回测通知"
                className="as-glass absolute -right-10 top-12 z-30 w-80 max-w-[calc(100vw-40px)] overflow-hidden rounded-2xl border border-as-border shadow-as-lg as-scale-in"
              >
                <div className="border-b border-as-border p-4 text-xs font-semibold">
                  最近的研究动态
                </div>
                {backtests.isError ? (
                  <p className="p-6 text-xs leading-relaxed text-as-muted">
                    研究服务暂未连接，恢复连接后可查看动态。
                  </p>
                ) : backtests.isLoading ? (
                  <p className="p-6 text-xs text-as-muted">正在读取动态…</p>
                ) : !recent.length ? (
                  <p className="p-6 text-xs leading-relaxed text-as-muted">
                    这里很安静。运行回测后，研究进展会显示在这里。
                  </p>
                ) : (
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
          aria-label="工作区设置"
          className="as-icon-well h-9 w-9 rounded-full text-[11px] font-semibold"
        >
          A
        </Link>
      </div>
      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
    </header>
  );
}
