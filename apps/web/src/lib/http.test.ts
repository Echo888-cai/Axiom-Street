import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("API transport", () => {
  it("uses the same-origin gateway by default", async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({ status: "ok" }));
    vi.stubGlobal("fetch", fetcher);
    await api.health();
    expect(fetcher.mock.calls[0][0]).toBe("/api/backend/health");
  });
  it("preserves structured validation errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { detail: { message: "日期范围无效" } },
            { status: 422 },
          ),
        ),
    );
    await expect(api.listStrategies()).rejects.toThrow("日期范围无效");
  });
  it("explains a disconnected backend without exposing browser fetch errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(api.health()).rejects.toThrow("无法连接研究服务");
  });
  it("supports no-content deletes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );
    await expect(api.deleteStrategy("example")).resolves.toBeUndefined();
  });
  it("routes event streams through the same gateway", () => {
    expect(api.eventsUrl("run-1")).toBe(
      "/api/backend/api/v1/backtests/run-1/events",
    );
  });
});
