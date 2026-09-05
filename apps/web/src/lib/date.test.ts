import { afterEach, expect, it, vi } from "vitest";
import { formatRelative } from "./utils";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
});
it("treats naive database timestamps as UTC, including in Shanghai", () => {
  vi.stubEnv("TZ", "Asia/Shanghai");
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-05T05:00:30Z"));
  expect(formatRelative("2026-09-05T05:00:00")).toBe("刚刚");
});
it("keeps explicit offsets intact", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-05T05:00:30Z"));
  expect(formatRelative("2026-09-05T12:30:00+08:00")).toBe("30 分钟前");
  expect(formatRelative("invalid")).toBe("—");
});
