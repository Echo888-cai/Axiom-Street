"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NAV_ITEMS } from "./nav";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

function StatusRow({
  ok,
  warn,
  label,
  detail,
}: {
  ok: boolean;
  warn?: boolean;
  label: string;
  detail: React.ReactNode;
}) {
  return (
    <div className="mt-2.5 first:mt-0">
      <div className="flex items-center gap-2 text-xs text-as-text">
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            ok ? "bg-as-positive" : warn ? "bg-[#F79009]" : "bg-as-negative",
            ok && "as-live-dot",
          )}
        />
        {label}
      </div>
      <p className="mt-0.5 pl-3.5 text-[11px] leading-relaxed text-as-muted">{detail}</p>
    </div>
  );
}

const SECTIONS = [
  { label: "研究", hrefs: ["/", "/strategies", "/backtests", "/universes"] },
  { label: "稍后", hrefs: ["/experiments", "/paper", "/live", "/risk", "/reports"] },
  { label: "系统", hrefs: ["/settings"] },
];

export function AppSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
    retry: 1,
  });
  const data = useQuery({
    queryKey: ["data-status"],
    queryFn: api.dataStatus,
    refetchInterval: 20000,
    retry: 1,
  });

  const apiOk = health.isSuccess;
  const dockerOk = Boolean(data.data?.lean_engine?.docker_available);
  const dataOk = Boolean(data.data?.ready);
  const symbols = data.data?.symbols?.length
    ? data.data.symbols.join(", ")
    : null;
  const dockerNote = data.data?.lean_engine?.note;

  return (
    <aside
      className={cn(
        "flex h-screen shrink-0 flex-col border-r border-as-border bg-as-bg transition-[width] duration-300",
        collapsed ? "w-[72px]" : "w-[232px]",
      )}
    >
      <div className={cn("flex items-center gap-3 px-4 py-5", collapsed && "justify-center px-2")}>
        <div className="relative flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-white ring-1 ring-as-border">
          <Image
            src="/logo.png"
            alt="Axiom Street"
            width={36}
            height={36}
            className="h-8 w-8 object-contain"
            priority
          />
        </div>
        {!collapsed ? (
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold tracking-tight text-as-text">
              Axiom Street
            </div>
            <div className="truncate text-[11px] text-as-muted">Honest Quant Research</div>
          </div>
        ) : null}
      </div>

      <nav className="flex-1 space-y-4 overflow-auto px-3 pb-3">
        {SECTIONS.map((section) => {
          const items = NAV_ITEMS.filter((item) =>
            (section.hrefs as readonly string[]).includes(item.href),
          );
          return (
            <div key={section.label}>
              {!collapsed ? (
                <div className="px-3 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-as-muted">
                  {section.label}
                </div>
              ) : null}
              <div className="space-y-0.5">
                {items.map((item) => {
                  const active =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname === item.href || pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      title={item.label}
                      className={cn(
                        "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all duration-as",
                        active
                          ? "bg-[rgba(22,119,255,0.08)] font-medium text-as-primary"
                          : "text-as-muted hover:bg-as-secondary hover:text-as-text",
                        collapsed && "justify-center px-2",
                      )}
                    >
                      <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.8} />
                      {!collapsed ? item.label : null}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      <div className="space-y-3 border-t border-as-border p-3">
        {!collapsed ? (
          <div className="rounded-as border border-as-border bg-as-secondary/60 p-3">
            <StatusRow
              ok={apiOk}
              label="系统状态"
              detail={apiOk ? "API 运行正常" : "API 未连接（端口 8000）"}
            />
            <StatusRow
              ok={dataOk}
              label="行情数据"
              detail={dataOk ? `${symbols || "行情"} 已就绪` : "尚未拉取行情"}
            />
            <StatusRow
              ok={dockerOk}
              warn={!dockerOk}
              label="回测引擎"
              detail={
                dockerOk ? (
                  "LEAN / Docker 可用"
                ) : (
                  <Link href="/settings" className="text-as-primary">
                    {dockerNote || "Worker 尚未上报 Docker 状态"}
                  </Link>
                )
              }
            />
          </div>
        ) : null}
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl px-3 py-2 text-xs text-as-muted transition-colors hover:bg-as-secondary hover:text-as-text"
        >
          <ChevronLeft
            className={cn("h-4 w-4 transition-transform duration-as", collapsed && "rotate-180")}
          />
          {!collapsed ? "收起" : null}
        </button>
      </div>
    </aside>
  );
}
