export type DiffLine = {
  kind: "same" | "add" | "del";
  text: string;
  a?: number;
  b?: number;
};

export type DiffSummary = {
  added: number;
  removed: number;
  lines: DiffLine[];
};

function lcsLengths(a: string[], b: string[]): number[][] {
  const rows = a.length;
  const cols = b.length;
  const dp: number[][] = Array.from({ length: rows + 1 }, () => Array(cols + 1).fill(0));
  for (let i = 1; i <= rows; i += 1) {
    for (let j = 1; j <= cols; j += 1) {
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }
  return dp;
}

export function diffLines(before: string, after: string): DiffSummary {
  const a = before.split("\n");
  const b = after.split("\n");
  const dp = lcsLengths(a, b);
  const lines: DiffLine[] = [];
  let i = a.length;
  let j = b.length;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      lines.push({ kind: "same", text: a[i - 1], a: i, b: j });
      i -= 1;
      j -= 1;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      lines.push({ kind: "add", text: b[j - 1], b: j });
      j -= 1;
    } else {
      lines.push({ kind: "del", text: a[i - 1], a: i });
      i -= 1;
    }
  }
  lines.reverse();
  return {
    added: lines.filter((l) => l.kind === "add").length,
    removed: lines.filter((l) => l.kind === "del").length,
    lines,
  };
}
