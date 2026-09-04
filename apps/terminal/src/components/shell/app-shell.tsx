import { Outlet } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useApp } from "@/store/app";
import { Sidebar } from "./sidebar";
import { Copilot } from "./copilot";
import { CommandPalette } from "@/components/ui/command-palette";

function Toaster() {
  const { toasts, dismissToast } = useApp();
  return (
    <div className="pointer-events-none fixed right-3.5 bottom-3.5 z-50 flex w-[300px] flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="pointer-events-auto flex items-start gap-2.5 rounded-lg border border-edge-strong bg-overlay p-3 shadow-[0_12px_40px_rgba(0,0,0,0.5)]"
          >
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-text">{t.title}</div>
              {t.detail && <div className="mono mt-0.5 truncate text-[10.5px] text-text-3">{t.detail}</div>}
            </div>
            <button
              onClick={() => dismissToast(t.id)}
              className="interactive cursor-pointer text-text-4 hover:text-text-2"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

/**
 * One shell for the whole product: Sidebar · Workspace · Copilot.
 * Pages never rebuild layout — they only fill the workspace.
 */
export function AppShell() {
  const copilotOpen = useApp((s) => s.copilotOpen);
  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex min-w-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">
          <Outlet />
        </main>
        <AnimatePresence>{copilotOpen && <Copilot />}</AnimatePresence>
      </div>
      <CommandPalette />
      <Toaster />
    </div>
  );
}
