import { type ValidationRun } from "@/lib/api";

export function isInflight(row: ValidationRun): boolean {
  return row.status === "QUEUED" || row.status === "RUNNING";
}

export function conclusion(row: ValidationRun) {
  if (row.status === "QUEUED" || row.status === "RUNNING") {
    return { tone: "blue" as const, label: row.progress_step || row.status };
  }
  if (row.error) return { tone: "red" as const, label: "失败" };
  if (row.kind === "DSR") {
    return row.passed
      ? { tone: "green" as const, label: "通过 95%" }
      : { tone: "amber" as const, label: "未过线" };
  }
  if (row.kind === "PBO") {
    return row.passed
      ? { tone: "green" as const, label: "PBO ≤ 0.5" }
      : { tone: "amber" as const, label: "PBO > 0.5" };
  }
  if (row.kind === "SENSITIVITY") {
    return row.passed
      ? { tone: "green" as const, label: "高原" }
      : { tone: "amber" as const, label: "孤峰" };
  }
  if (row.kind === "COST") {
    return row.passed
      ? { tone: "green" as const, label: "成本可承受" }
      : { tone: "amber" as const, label: "临界成本过低" };
  }
  if (row.kind === "BOOTSTRAP") {
    return row.passed
      ? { tone: "green" as const, label: "Sharpe CI > 0" }
      : { tone: "amber" as const, label: "区间跨零" };
  }
  if (row.kind === "REGIME") {
    if (row.passed && row.result.single_regime === true) {
      return { tone: "amber" as const, label: "edge 集中" };
    }
    return row.passed
      ? { tone: "green" as const, label: "跨制度稳健" }
      : { tone: "amber" as const, label: "单一制度" };
  }
  if (row.kind === "SPA") {
    return row.passed
      ? { tone: "green" as const, label: "SPA_c 拒绝无 edge" }
      : { tone: "amber" as const, label: "不能声称有 edge" };
  }
  return row.passed
    ? { tone: "green" as const, label: "通过" }
    : { tone: "amber" as const, label: "未通过" };
}
