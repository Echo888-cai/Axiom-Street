"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { NAV_ITEMS } from "@/components/layout/nav";
import { labelStatus } from "@/lib/labels";
import { formatPct } from "@/lib/utils";

type Hit = {
  href: string;
  title: string;
  meta: string;
  group: string;
};

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.listStrategies });
  const backtests = useQuery({ queryKey: ["backtests"], queryFn: api.listBacktests });

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    const t = window.setTimeout(() => inputRef.current?.focus(), 20);
    return () => window.clearTimeout(t);
  }, [open]);

  const hits = useMemo(() => {
    const q = query.trim().toLowerCase();
    const nav: Hit[] = NAV_ITEMS.filter(
      (item) =>
        !q ||
        item.label.toLowerCase().includes(q) ||
        item.href.toLowerCase().includes(q),
    ).map((item) => ({
      href: item.href,
      title: item.label,
      meta: "前往",
      group: "导航",
    }));
    const s: Hit[] = (strategies.data || [])
      .filter(
        (item) =>
          !q ||
          item.name.toLowerCase().includes(q) ||
          (item.description || "").toLowerCase().includes(q),
      )
      .slice(0, 6)
      .map((item) => ({
        href: `/strategies/${item.id}`,
        title: item.name,
        meta: labelStatus(item.status),
        group: "策略",
      }));
    const b: Hit[] = (backtests.data || [])
      .filter(
        (item) =>
          !q ||
          (item.strategy_name || "").toLowerCase().includes(q) ||
          item.benchmark.toLowerCase().includes(q) ||
          item.start_date.includes(q),
      )
      .slice(0, 5)
      .map((item) => ({
        href: `/backtests/${item.id}`,
        title: item.strategy_name || `${item.start_date} → ${item.end_date}`,
        meta: `${item.start_date} → ${item.end_date}${
          item.total_return != null ? ` · ${formatPct(item.total_return)}` : ""
        }`,
        group: "回测",
      }));
    return [...nav, ...s, ...b];
  }, [query, strategies.data, backtests.data]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  function go(href: string) {
    onClose();
    router.push(href);
  }

  if (!open) return null;

  const groups = ["导航", "策略", "回测"].filter((g) => hits.some((h) => h.group === g));

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center px-4 pt-[14vh]">
      <button
        type="button"
        className="absolute inset-0 bg-[rgba(15,23,42,0.28)] aq-fade"
        aria-label="关闭命令盘"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="命令盘"
        className="relative w-full max-w-[560px] overflow-hidden rounded-aq border border-aq-border bg-aq-bg shadow-aq-lg aq-scale-in"
      >
        <div className="flex items-center gap-2 border-b border-aq-border px-4">
          <Search className="h-4 w-4 text-aq-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索策略、回测、页面…"
            className="h-12 w-full bg-transparent text-sm text-aq-text outline-none placeholder:text-aq-muted"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((v) => Math.min(v + 1, Math.max(hits.length - 1, 0)));
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((v) => Math.max(v - 1, 0));
              }
              if (e.key === "Enter" && hits[active]) go(hits[active].href);
              if (e.key === "Escape") onClose();
            }}
          />
        </div>
        <div className="max-h-[420px] overflow-auto py-2">
          {!hits.length ? (
            <p className="px-4 py-10 text-center text-sm text-aq-muted">没有匹配结果</p>
          ) : (
            groups.map((group) => {
              const items = hits.filter((h) => h.group === group);
              return (
                <div key={group} className="px-2 py-1">
                  <div className="px-2 py-1.5 text-[10px] font-medium uppercase tracking-wider text-aq-muted">
                    {group}
                  </div>
                  {items.map((hit) => {
                    const index = hits.indexOf(hit);
                    return (
                      <button
                        key={hit.href + hit.title}
                        type="button"
                        onMouseEnter={() => setActive(index)}
                        onClick={() => go(hit.href)}
                        className={`flex w-full cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm ${
                          index === active ? "bg-aq-secondary" : ""
                        }`}
                      >
                        <span className="truncate text-aq-text">{hit.title}</span>
                        <span className="ml-3 shrink-0 text-[11px] text-aq-muted">{hit.meta}</span>
                      </button>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>
        <div className="flex items-center gap-3 border-t border-aq-border bg-aq-secondary/50 px-4 py-2 text-[11px] text-aq-muted">
          <span>
            <kbd className="rounded border border-aq-border bg-aq-bg px-1">↑↓</kbd> 选择
          </span>
          <span>
            <kbd className="rounded border border-aq-border bg-aq-bg px-1">↵</kbd> 打开
          </span>
          <span>
            <kbd className="rounded border border-aq-border bg-aq-bg px-1">esc</kbd> 关闭
          </span>
        </div>
      </div>
    </div>
  );
}
