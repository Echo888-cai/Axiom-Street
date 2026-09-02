"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, Search } from "lucide-react";
import { api } from "@/lib/api";
import { BACKTEST_TONE, labelStatus } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { CommandPalette } from "@/components/ui/command-palette";
import { formatRelative } from "@/lib/utils";
import Link from "next/link";

export function TopBar() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);

  const backtests = useQuery({
    queryKey: ["backtests"],
    queryFn: api.listBacktests,
    refetchInterval: 8000,
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setNotesOpen(false);
        setSearchOpen(true);
      }
      if (e.key === "Escape") setNotesOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const recentNotes = (backtests.data || []).slice(0, 6);
  const hasAlert = recentNotes.some((b) => b.status === "COMPLETED" || b.status === "FAILED");

  return (
    <header className="flex h-14 items-center justify-between gap-4 border-b border-as-border bg-as-bg/90 px-6 backdrop-blur-sm">
      <button
        type="button"
        onClick={() => setSearchOpen(true)}
        className="flex h-9 w-full max-w-xl cursor-pointer items-center gap-2 rounded-xl border border-transparent bg-as-secondary/70 px-3 text-left text-sm text-as-muted transition-colors hover:border-as-border hover:bg-as-secondary"
      >
        <Search className="h-4 w-4" />
        <span className="flex-1">搜索策略、回测、页面…</span>
        <kbd className="rounded-md border border-as-border bg-as-bg px-1.5 py-0.5 text-[10px]">
          ⌘K
        </kbd>
      </button>

      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />

      <div className="relative flex items-center gap-3">
        <button
          type="button"
          className="relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-full text-as-muted transition-colors hover:bg-as-secondary hover:text-as-text"
          aria-label="通知"
          onClick={() => setNotesOpen((v) => !v)}
        >
          <Bell className="h-4 w-4" />
          {hasAlert ? (
            <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-as-primary" />
          ) : null}
        </button>
        {notesOpen ? (
          <>
            <button
              type="button"
              className="fixed inset-0 z-20 cursor-default"
              aria-label="关闭通知"
              onClick={() => setNotesOpen(false)}
            />
            <div className="absolute right-0 top-11 z-30 w-80 overflow-hidden rounded-as border border-as-border bg-as-bg shadow-as-lg as-scale-in">
              <div className="border-b border-as-border px-3 py-2.5 text-xs font-medium text-as-text">
                通知
              </div>
              {!recentNotes.length ? (
                <p className="px-3 py-8 text-center text-sm text-as-muted">
                  暂无通知。回测完成或失败后会显示在这里。
                </p>
              ) : (
                <ul className="max-h-80 overflow-auto py-1">
                  {recentNotes.map((b) => (
                    <li key={b.id}>
                      <Link
                        href={`/backtests/${b.id}`}
                        className="block px-3 py-2.5 text-sm hover:bg-as-secondary"
                        onClick={() => setNotesOpen(false)}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-as-text">
                            {b.strategy_name || `${b.start_date} → ${b.end_date}`}
                          </span>
                          <Badge tone={BACKTEST_TONE[b.status] || "blue"}>
                            {labelStatus(b.status)}
                          </Badge>
                        </div>
                        <p className="mt-0.5 text-[11px] text-as-muted">
                          {formatRelative(b.finished_at || b.created_at)}
                        </p>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        ) : null}

        <div className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(22,119,255,0.12)] text-xs font-semibold text-as-primary">
            本
          </div>
          <div className="hidden sm:block">
            <div className="text-sm font-medium leading-tight text-as-text">本地用户</div>
            <div className="text-[11px] text-as-muted">研究者</div>
          </div>
        </div>
      </div>
    </header>
  );
}
