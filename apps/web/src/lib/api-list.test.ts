import { describe, expect, it } from "vitest";
import { unwrapList, type Page } from "./api";

describe("unwrapList", () => {
  it("returns arrays unchanged", () => {
    expect(unwrapList([1, 2])).toEqual([1, 2]);
  });

  it("unwraps paginated payloads", () => {
    const page: Page<string> = { items: ["a"], total: 1, limit: 50, offset: 0 };
    expect(unwrapList(page)).toEqual(["a"]);
  });
});
