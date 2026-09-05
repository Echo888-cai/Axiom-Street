"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowUpRight,
  ChevronsUpDown,
  PanelLeftClose,
  PanelLeftOpen,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NAV_ITEMS } from "./nav";
import { AxiomMark } from "@/components/brand/axiom-mark";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const SECTIONS = [
  {
    label: "工作空间",
    english: "WORKSPACE",
    hrefs: [
      "/",
      "/strategies",
      "/backtests",
      "/validation",
      "/universes",
      "/experiments",
      "/reports",
    ],
  },
  {
    label: "交易与风险",
    english: "EXECUTION",
    hrefs: ["/paper", "/live", "/risk"],
  },
];

function NavigationContent({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });
  return (
    <>
      <Link
        href="/"
        onClick={onNavigate}
        aria-label="Axiom Street 首页"
        className={cn(
          "flex h-[94px] items-center gap-3 px-6",
          collapsed && "justify-center px-3",
        )}
      >
        <AxiomMark className="h-9 w-9 shrink-0 text-[#303b4c]" />
        {!collapsed && (
          <div>
            <div className="text-[16px] font-semibold tracking-[-.04em]">
              Axiom Street<span className="ml-0.5 text-as-primary">.</span>
            </div>
            <div className="mt-0.5 text-[9px] tracking-[.2em] text-as-muted">
              RESEARCH STUDIO
            </div>
          </div>
        )}
      </Link>
      {!collapsed && (
        <Link
          href="/settings"
          onClick={onNavigate}
          className="as-button-secondary mx-4 mb-5 flex items-center gap-2.5 rounded-xl border border-as-border p-3"
        >
          <span className="as-icon-well h-8 w-8 rounded-lg text-[11px] font-semibold">
            A
          </span>
          <span className="flex-1">
            <span className="block text-xs font-medium">个人研究空间</span>
            <span className="mt-0.5 block text-[10px] text-as-muted">
              本地工作区
            </span>
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 text-as-muted" />
        </Link>
      )}
      <nav
        aria-label="主导航"
        className="flex-1 space-y-7 overflow-y-auto px-3"
      >
        {SECTIONS.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <div className="mb-2.5 flex items-center justify-between px-3 text-[10px] text-as-muted">
                <span>{section.label}</span>
                <span className="text-[8px] tracking-[.13em] opacity-75">
                  {section.english}
                </span>
              </div>
            )}
            <div className="space-y-1">
              {NAV_ITEMS.filter((item) =>
                section.hrefs.includes(item.href),
              ).map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname === item.href ||
                      pathname.startsWith(`${item.href}/`);
                const planned = ["/paper", "/live", "/risk"].includes(
                  item.href,
                );
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    title={item.label}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group relative flex min-h-11 items-center gap-3 rounded-xl border border-transparent px-3 text-[13px] transition-all duration-200",
                      active
                        ? "border-white bg-white font-medium text-as-text shadow-[0_2px_7px_-3px_rgba(30,42,62,.15)]"
                        : "text-as-muted hover:bg-white/70 hover:text-as-text",
                      collapsed && "justify-center px-2",
                    )}
                  >
                    <item.icon
                      className={cn(
                        "h-[18px] w-[18px] shrink-0",
                        active && "text-as-primary",
                      )}
                      strokeWidth={1.65}
                    />
                    {!collapsed && (
                      <>
                        <span className="flex-1">{item.label}</span>
                        {active ? (
                          <span className="h-1 w-1 rounded-full bg-as-primary" />
                        ) : planned ? (
                          <span className="rounded border border-as-border px-1 text-[8px] tracking-wide text-as-muted">
                            规划中
                          </span>
                        ) : null}
                      </>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="mt-6 space-y-4 p-4">
        {!collapsed && (
          <div className="as-sidebar-note rounded-2xl border border-white bg-white/45 p-4">
            <div className="mb-2 text-[11px] font-medium">
              少一点噪音，多一点确信。
            </div>
            <p className="text-[10px] leading-relaxed text-as-muted">
              从假设出发，让证据说话。
            </p>
            <Link
              href="/reports"
              onClick={onNavigate}
              className="mt-3 inline-flex items-center gap-1 text-[10px] text-as-primary"
            >
              打开研究笔记 <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
        )}
        <Link
          href="/settings"
          onClick={onNavigate}
          title="设置与服务状态"
          className={cn(
            "flex min-h-11 items-center gap-2.5 rounded-xl px-2 text-xs text-as-muted hover:bg-white",
            collapsed && "justify-center px-0",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 shrink-0 rounded-full",
              health.isLoading
                ? "bg-as-muted"
                : health.isError
                  ? "bg-amber-500"
                  : "bg-as-positive",
            )}
          />
          {!collapsed && (
            <>
              <span className="flex-1">
                {health.isLoading
                  ? "正在连接"
                  : health.isError
                    ? "服务未连接"
                    : "研究服务已连接"}
              </span>
              <NAV_SETTINGS_ICON />
            </>
          )}
        </Link>
      </div>
    </>
  );
}

function NAV_SETTINGS_ICON() {
  const Icon = NAV_ITEMS.find((item) => item.href === "/settings")!.icon;
  return <Icon className="h-4 w-4" strokeWidth={1.6} />;
}

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <aside
      className={cn(
        "as-glass sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-white/80 transition-[width] duration-300 md:flex",
        collapsed ? "w-[76px]" : "w-[232px] xl:w-[248px]",
      )}
    >
      <NavigationContent collapsed={collapsed} />
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        aria-label={collapsed ? "展开侧栏" : "收起侧栏"}
        className="mx-4 mb-4 flex min-h-9 items-center justify-center gap-2 rounded-lg text-[10px] text-as-muted hover:bg-white/70"
      >
        {collapsed ? (
          <PanelLeftOpen className="h-4 w-4" />
        ) : (
          <>
            <PanelLeftClose className="h-3.5 w-3.5" /> 收起侧栏
          </>
        )}
      </button>
    </aside>
  );
}

export function MobileNavigation({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open) ref.current?.showModal();
    else ref.current?.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-label="移动导航"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className="fixed inset-0 m-0 h-dvh max-h-none w-[290px] max-w-[85vw] border-0 bg-[#f6f7f9] p-0 shadow-as-lg backdrop:bg-slate-900/15 backdrop:backdrop-blur-sm"
    >
      <div className="flex h-full flex-col">
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭导航"
          className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded-full text-as-muted hover:bg-white"
        >
          <X className="h-4 w-4" />
        </button>
        {open && <NavigationContent onNavigate={onClose} />}
      </div>
    </dialog>
  );
}
