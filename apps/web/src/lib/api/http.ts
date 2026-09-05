import type { Page } from "./types";

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "/api/backend"
).replace(/\/$/, "");

export function unwrapList<T>(data: T[] | Page<T>): T[] {
  return Array.isArray(data) ? data : data.items;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    const headers = new Headers(init?.headers);
    if (init?.body && !headers.has("Content-Type"))
      headers.set("Content-Type", "application/json");
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers,
      cache: "no-store",
      signal: init?.signal ?? AbortSignal.timeout(30_000),
    });
  } catch (error) {
    if (init?.signal?.aborted) throw error;
    if (error instanceof Error && error.name === "TimeoutError")
      throw new Error("研究服务响应超时，请稍后重试。");
    throw new Error("无法连接研究服务，请检查连接后重试。");
  }
  if (!res.ok) {
    const text = await res.text();
    let message = `请求失败（${res.status}），请稍后重试。`;
    try {
      const { detail } = JSON.parse(text) as { detail?: unknown };
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) message = detail[0]?.msg || message;
      else if (detail && typeof detail === "object") {
        const value = detail as { message?: string; msg?: string };
        message = value.message || value.msg || message;
      }
    } catch {
      /* A reverse proxy may return HTML. Keep the readable status message. */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
