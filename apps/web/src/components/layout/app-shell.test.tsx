import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/backtests/example" }));
vi.mock("./app-sidebar", () => ({ AppSidebar: () => null, MobileNavigation: () => null }));
vi.mock("./top-bar", () => ({ TopBar: ({ onAssistant }: { onAssistant?: () => void }) => <button onClick={onAssistant}>研究助手</button> }));
vi.mock("@/components/copilot/copilot-panel", () => ({ CopilotPanel: () => <p>研究上下文</p> }));
vi.mock("@/components/ui/toast", () => ({ ToastViewport: () => null }));

describe("focused workspace", () => {
  it("loads the assistant only when requested and closes it without hiding the workspace", () => {
    render(<AppShell><h1>回测详情</h1></AppShell>);
    expect(screen.queryByText("研究上下文")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "研究助手" }));
    expect(screen.getByRole("dialog", { name: "研究助手与验证" })).toBeVisible();
    expect(screen.getByText("研究上下文")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "关闭研究助手" }));
    expect(screen.queryByText("研究上下文")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "回测详情" })).toBeVisible();
  });
});
