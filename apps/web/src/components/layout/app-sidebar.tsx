"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  X,
} from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NAV_ITEMS } from "./nav";
import { AxiomMark } from "@/components/brand/axiom-mark";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";

const SECTIONS = [
  {
    label: "研究工作台",
    hrefs: ["/", "/strategies", "/backtests", "/validation"],
    primary: true,
  },
  {
    label: "研究资料",
    hrefs: ["/universes", "/experiments", "/reports", "/portfolios"],
    primary: false,
  },
  { label: "交易与风险", hrefs: ["/paper", "/risk", "/live"], primary: false },
];

function matchesRoute(pathname: string, href: string) {
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

function NavigationSection({
  section,
  collapsed,
  onNavigate,
}: {
  section: (typeof SECTIONS)[number];
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const t = useT();
  const pathname = usePathname();
  const id = useId();
  const activeSection = section.hrefs.some((href) =>
    matchesRoute(pathname, href),
  );
  const [expanded, setExpanded] = useState(activeSection);
  useEffect(() => {
    if (activeSection) setExpanded(true);
  }, [activeSection, pathname]);
  const open = collapsed || section.primary || expanded;

  return (
    <div
      className={cn("py-2", !section.primary && "border-t border-as-border/70")}
    >
      {!collapsed &&
        (section.primary ? (
          <p className="px-3 pb-2 pt-1 text-[11px] font-medium tracking-wide text-as-muted">
            {section.label}
          </p>
        ) : (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-controls={id}
            className="flex min-h-11 w-full items-center justify-between rounded-lg px-3 text-xs font-medium text-as-muted hover:bg-as-secondary hover:text-as-text"
          >
            {section.label}
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 transition-transform",
                !expanded && "-rotate-90",
              )}
              aria-hidden="true"
            />
          </button>
        ))}
      <div id={id} hidden={!open} className="space-y-1">
        {section.hrefs.map((href) => {
          const item = NAV_ITEMS.find((item) => item.href === href)!;
          const active = matchesRoute(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              title={t(`nav.${item.key}`)}
              aria-label={t(`nav.${item.key}`)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "as-nav-link flex min-h-12 items-center gap-2.5 rounded-xl px-2.5 text-[13px]",
                active
                  ? "as-nav-active font-semibold"
                  : "text-as-muted hover:bg-as-secondary hover:text-as-text",
                collapsed && "justify-center px-2",
              )}
            >
              <span className="as-nav-icon">
                <item.icon className="h-[18px] w-[18px]" aria-hidden="true" />
              </span>
              {!collapsed && (
                <>
                  <span className="flex-1">{t(`nav.${item.key}`)}</span>
                  {href === "/live" && (
                    <span className="text-[10px] opacity-70">
                      {t("layout.planned")}
                    </span>
                  )}
                </>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function NavigationContent({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const t = useT();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });
  const connected = !health.isError && health.data?.status === "ok";
  const status = health.isLoading
    ? t("layout.connecting")
    : connected
      ? t("layout.connected")
      : t("layout.disconnected");

  return (
    <>
      <Link
        href="/"
        onClick={onNavigate}
        aria-label={t("layout.homeAria")}
        className={cn(
          "flex h-[76px] shrink-0 items-center gap-2.5 px-5",
          collapsed && "justify-center px-3",
        )}
      >
        <AxiomMark className="h-8 w-8 shrink-0 text-as-text" />
        {!collapsed && (
          <div>
            <div className="text-[15px] font-semibold tracking-[-.04em]">
              Axiom Street<span className="text-as-primary">.</span>
            </div>
            <div className="text-[9px] tracking-[.18em] text-as-muted">
              RESEARCH STUDIO
            </div>
          </div>
        )}
      </Link>
      <nav
        aria-label={t("layout.mainNavAria")}
        className="min-h-0 flex-1 overflow-y-auto px-3"
      >
        {SECTIONS.map((section) => (
          <NavigationSection
            key={section.label}
            section={section}
            collapsed={collapsed}
            onNavigate={onNavigate}
          />
        ))}
      </nav>
      <div className="mx-3 mt-3 shrink-0 border-t border-as-border pt-3">
        <Link
          href="/settings"
          onClick={onNavigate}
          aria-label={t("layout.workspaceSettings")}
          title={`${t("layout.workspaceSettings")} · ${status}`}
          className={cn(
            "flex min-h-12 items-center gap-2.5 rounded-lg px-2 hover:bg-as-secondary",
            collapsed && "justify-center px-0",
          )}
        >
          <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-as-primary/10 text-[11px] font-semibold text-as-primary">
            A
            <span
              className={cn(
                "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white",
                health.isLoading
                  ? "bg-as-muted"
                  : connected
                    ? "bg-as-positive"
                    : "bg-amber-500",
              )}
            />
          </span>
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block text-xs font-medium">
                  {t("layout.personalSpace")}
                </span>
                <span className="mt-0.5 block text-[10px] text-as-muted">
                  {status}
                </span>
              </span>
              <Settings className="h-4 w-4 text-as-muted" aria-hidden="true" />
            </>
          )}
        </Link>
      </div>
    </>
  );
}

export function AppSidebar() {
  const t = useT();
  const [collapsed, setCollapsed] = useState(false);
  return (
    <aside
      className={cn(
        "as-sidebar sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-as-border transition-[width] duration-200 md:flex",
        collapsed ? "w-[68px]" : "w-[208px]",
      )}
    >
      <NavigationContent collapsed={collapsed} />
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        aria-expanded={!collapsed}
        aria-label={
          collapsed
            ? t("layout.expandSidebarAria")
            : t("layout.collapseSidebarAria")
        }
        className="mx-3 mb-3 mt-1 flex min-h-9 items-center justify-center gap-2 rounded-lg text-[11px] text-as-muted hover:bg-as-secondary"
      >
        {collapsed ? (
          <PanelLeftOpen className="h-4 w-4" />
        ) : (
          <>
            <PanelLeftClose className="h-3.5 w-3.5" />
            {t("layout.collapseSidebarAria")}
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
  const t = useT();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open) ref.current?.showModal();
    else ref.current?.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-label={t("layout.mobileNavAria")}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className="fixed inset-0 m-0 h-dvh max-h-none w-[290px] max-w-[85vw] border-0 bg-as-bg p-0 shadow-as-lg backdrop:bg-slate-900/15 backdrop:backdrop-blur-sm"
    >
      <div className="flex h-full flex-col">
        <button
          type="button"
          onClick={onClose}
          aria-label={t("layout.closeNavAria")}
          className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded-full text-as-muted hover:bg-white"
        >
          <X className="h-4 w-4" />
        </button>
        {open && <NavigationContent onNavigate={onClose} />}
      </div>
    </dialog>
  );
}
