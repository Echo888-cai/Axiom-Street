import { describe, expect, it } from "vitest";
import { diffLines } from "./diff";

describe("diffLines", () => {
  it("counts added and removed lines", () => {
    const before = "a\nb\nc\n";
    const after = "a\nx\nc\n";
    const diff = diffLines(before, after);
    expect(diff.added).toBe(1);
    expect(diff.removed).toBe(1);
    expect(diff.lines.filter((l) => l.kind !== "same").map((l) => [l.kind, l.text])).toEqual([
      ["del", "b"],
      ["add", "x"],
    ]);
  });

  it("treats identical files as zero churn", () => {
    const diff = diffLines("same\n", "same\n");
    expect(diff.added).toBe(0);
    expect(diff.removed).toBe(0);
  });
});
