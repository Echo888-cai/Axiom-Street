"use client";

import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { X } from "lucide-react";
import { useState } from "react";
import { AppSidebar, MobileNavigation } from "./app-sidebar";
import { TopBar } from "./top-bar";
import { CopilotPanel } from "@/components/copilot/copilot-panel";
import { ToastViewport } from "@/components/ui/toast";
import { useT } from "@/lib/i18n";

export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useT();
  const pathname = usePathname();
  const hasContext = /^\/(strategies|backtests)\/[^/]+$/.test(pathname);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="as-workspace flex min-h-screen">
      <a
        href="#main-content"
        className="fixed left-4 top-4 z-[100] -translate-y-24 rounded-xl bg-white p-3 text-sm shadow-as-lg focus:translate-y-0"
      >
        {t("layout.skipToMain")}
      </a>
      <AppSidebar />
      <MobileNavigation open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenu={() => setMenuOpen(true)} onAssistant={hasContext ? () => setAssistantOpen(true) : undefined} />
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-[1440px] flex-1 px-5 pb-12 pt-8 outline-none sm:px-8 lg:px-10 lg:pt-11 xl:px-12"
        >
          {children}
        </main>
        <footer className="mx-5 flex flex-wrap items-center justify-between gap-2 border-t border-as-border py-5 text-[11px] tracking-wide text-as-muted sm:mx-8 lg:mx-10 xl:mx-12">
          <span>
            <span className="font-semibold tracking-[.12em]">AXIOM STREET</span> <span className="mx-2 opacity-40">/</span> HONEST RESEARCH
          </span>
          <span>{t("layout.tagline")}</span>
        </footer>
      </div>
      <Modal open={assistantOpen} onClose={() => setAssistantOpen(false)} label="研究助手与验证" className="max-w-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-as-border bg-white/95 px-6 py-4 backdrop-blur-xl">
          <div><h2 className="text-base font-semibold">研究助手与验证</h2><p className="mt-1 text-xs text-as-muted">理解研究证据，检查下一步。</p></div>
          <Button variant="ghost" onClick={() => setAssistantOpen(false)} aria-label="关闭研究助手"><X className="h-4 w-4" /></Button>
        </div>
        <CopilotPanel expanded />
      </Modal>
      <ToastViewport />
    </div>
  );
}
