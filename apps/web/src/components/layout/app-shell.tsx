import { AppSidebar } from "./app-sidebar";
import { TopBar } from "./top-bar";
import { ToastViewport } from "@/components/ui/toast";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-aq-secondary">
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-auto p-6 md:p-8">{children}</main>
      </div>
      <ToastViewport />
    </div>
  );
}
