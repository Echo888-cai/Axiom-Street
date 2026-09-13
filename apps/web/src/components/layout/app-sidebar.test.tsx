import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { AppSidebar } from "./app-sidebar";

let pathname = "/strategies";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/lib/api", () => ({ api: { health: () => new Promise(() => {}) } }));

function sidebar() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AppSidebar />
    </QueryClientProvider>,
  );
}

describe("compact research navigation", () => {
  it("keeps settings identifiable when only icons are visible", () => {
    pathname = "/strategies";
    sidebar();
    fireEvent.click(screen.getByRole("button", { name: "收起侧栏" }));
    expect(
      screen.getByRole("link", { name: "设置与服务状态" }),
    ).toHaveAttribute("href", "/settings");
  });
  it("keeps research visible and reveals secondary tools on demand", () => {
    pathname = "/strategies";
    sidebar();
    expect(screen.getByRole("link", { name: "策略实验室" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.queryByRole("link", { name: "研究笔记" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "研究资料" }));
    expect(screen.getByRole("link", { name: "研究笔记" })).toBeVisible();
  });

  it("reveals the active secondary section when opening a deep link", () => {
    pathname = "/risk";
    sidebar();
    expect(screen.getByRole("button", { name: "交易与风险" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByRole("link", { name: "风控" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});
