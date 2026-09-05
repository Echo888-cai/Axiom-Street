import { afterEach, expect, it, vi } from "vitest";
import { proxyBackend } from "./proxy";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
it("forwards query, JSON body and upstream status to the runtime origin", async () => {
  vi.stubEnv("API_BASE_URL", "http://api:8000");
  const fetcher = vi
    .fn()
    .mockResolvedValue(Response.json({ id: "created" }, { status: 201 }));
  vi.stubGlobal("fetch", fetcher);
  const result = await proxyBackend(
    new Request("http://localhost/api/backend/api/v1/strategies?limit=5", {
      method: "POST",
      body: '{"name":"test"}',
      headers: { "Content-Type": "application/json" },
    }),
    ["api", "v1", "strategies"],
  );
  expect(String(fetcher.mock.calls[0][0])).toBe(
    "http://api:8000/api/v1/strategies?limit=5",
  );
  expect(fetcher.mock.calls[0][1].method).toBe("POST");
  expect(new TextDecoder().decode(fetcher.mock.calls[0][1].body)).toBe(
    '{"name":"test"}',
  );
  expect(result.status).toBe(201);
});
it("preserves SSE without buffering", async () => {
  const stream = new ReadableStream({
    start(c) {
      c.enqueue(new TextEncoder().encode("event: done\ndata: {}\n\n"));
      c.close();
    },
  });
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(stream, {
          headers: { "Content-Type": "text/event-stream" },
        }),
      ),
  );
  const result = await proxyBackend(new Request("http://localhost/events"), [
    "api",
    "v1",
    "backtests",
    "run",
    "events",
  ]);
  expect(result.headers.get("content-type")).toBe("text/event-stream");
  expect(result.body).toBe(stream);
  expect(await result.text()).toContain("event: done");
});
it("returns a readable 502 when the engine is offline", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
  const result = await proxyBackend(new Request("http://localhost/health"), [
    "health",
  ]);
  expect(result.status).toBe(502);
  expect((await result.json()).detail.message).toContain("研究服务");
});
it("rejects traversal and paths outside the API", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  for (const path of [
    ["api", "v1", "..", "private"],
    ["private"],
    ["api", "v1", "%2e%2e"],
  ]) {
    expect(
      (await proxyBackend(new Request("http://localhost/"), path)).status,
    ).toBe(400);
  }
  expect(fetcher).not.toHaveBeenCalled();
});
