"use client";

import { useState } from "react";
import { AppSidebar, MobileNavigation } from "./app-sidebar";
import { TopBar } from "./top-bar";
import { ToastViewport } from "@/components/ui/toast";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="as-workspace flex min-h-screen">
      <a
        href="#main-content"
        className="fixed left-4 top-4 z-[100] -translate-y-24 rounded-xl bg-white p-3 text-sm shadow-as-lg focus:translate-y-0"
      >
        跳到主要内容
      </a>
      <AppSidebar />
      <MobileNavigation open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenu={() => setMenuOpen(true)} />
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-[1600px] flex-1 px-5 pb-8 pt-7 outline-none sm:px-8 lg:px-10 lg:pt-9 xl:px-12"
        >
          {children}
        </main>
        <footer className="mx-5 flex flex-wrap items-center justify-between gap-2 border-t border-as-border py-5 text-[10px] tracking-wide text-as-muted sm:mx-8 lg:mx-10 xl:mx-12">
          <span>
            AXIOM STREET <span className="mx-2 opacity-40">/</span> HONEST QUANT
            RESEARCH
          </span>
          <span>让每一个结论，都经得起验证。</span>
        </footer>
      </div>
      <ToastViewport />
    </div>
  );
}
