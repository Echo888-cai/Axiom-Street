/** Runtime gateway for JSON, downloads and server-sent events. Never buffers responses. */
export async function proxyBackend(
  request: Request,
  path: string[],
): Promise<Response> {
  const allowed =
    path.join("/") === "health" || (path[0] === "api" && path[1] === "v1");
  if (
    !allowed ||
    path.some(
      (part) =>
        !/^[a-zA-Z0-9_.-]+$/.test(part) || part === "." || part === "..",
    )
  ) {
    return Response.json({ detail: "无效的服务路径" }, { status: 400 });
  }
  const origin = process.env.API_BASE_URL || "http://127.0.0.1:8000";
  const target = new URL(`/${path.join("/")}`, origin);
  target.search = new URL(request.url).search;
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (request.signal.aborted) controller.abort();
  else request.signal.addEventListener("abort", abort, { once: true });
  // Limit waiting for headers, but allow long-running SSE after connection.
  const timer = setTimeout(abort, 30_000);
  try {
    const headers = new Headers();
    for (const key of [
      "content-type",
      "accept",
      "last-event-id",
      "x-request-id",
    ]) {
      const value = request.headers.get(key);
      if (value) headers.set(key, value);
    }
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method)
        ? undefined
        : await request.arrayBuffer(),
      signal: controller.signal,
      cache: "no-store",
      redirect: "manual",
    });
    const responseHeaders = new Headers();
    for (const key of ["content-type", "content-disposition", "x-request-id"]) {
      const value = upstream.headers.get(key);
      if (value) responseHeaders.set(key, value);
    }
    responseHeaders.set("Cache-Control", "no-store");
    responseHeaders.set("X-Accel-Buffering", "no");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      {
        detail: {
          code: "backend_unavailable",
          message: "无法连接研究服务，请检查服务状态后重试。",
        },
      },
      { status: 502 },
    );
  } finally {
    clearTimeout(timer);
  }
}
