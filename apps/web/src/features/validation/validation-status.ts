import { type ValidationRun } from "@/lib/api";
import { tr } from "@/lib/translate";

export function isInflight(row: ValidationRun): boolean {
  return row.status === "QUEUED" || row.status === "RUNNING";
}

export function conclusion(row: ValidationRun) {
  if (row.status === "QUEUED" || row.status === "RUNNING") {
    return { tone: "blue" as const, label: row.progress_step || row.status };
  }
  if (row.error) return { tone: "red" as const, label: tr("validation.status.failed") };
  if (row.kind === "DSR") {
    return row.passed
      ? { tone: "green" as const, label: tr("validation.conclusion.dsrPassed") }
      : { tone: "amber" as const, label: tr("validation.conclusion.dsrFailed") };
  }
  if (row.kind === "PBO") {
    return row.passed
      ? { tone: "green" as const, label: tr("validation.conclusion.pboPassed") }
      : { tone: "amber" as const, label: tr("validation.conclusion.pboFailed") };
  }
  if (row.kind === "SENSITIVITY") {
    return row.passed
      ? { tone: "green" as const, label: tr("validation.shapes.plateau") }
      : { tone: "amber" as const, label: tr("validation.shapes.knifeEdge") };
  }
  if (row.kind === "COST") {
    return row.passed
      ? { tone: "green" as const, label: tr("validation.conclusion.costPassed") }
      : { tone: "amber" as const, label: tr("validation.conclusion.costFailed") };
  }
  if (row.kind === "BOOTSTRAP") {
    return row.passed
      ? { tone: "green" as const, label: tr("validation.conclusion.bootstrapPassed") }
      : { tone: "amber" as const, label: tr("validation.conclusion.bootstrapFailed") };
  }
  if (row.kind === "REGIME") {
    if (row.passed && row.result?.single_regime === true) {
      return { tone: "amber" as const, label: tr("validation.conclusion.edgeConcentrated") };
    }
    return row.passed
      ? { tone: "green" as const, label: tr("validation.conclusion.robustAcrossRegimes") }
      : { tone: "amber" as const, label: tr("validation.reports.regime.singleRegime") };
  }
  if (row.kind === "SPA") {
    return row.passed
      ? { tone: "green" as const, label: tr("validation.conclusion.spaRejectsNoEdge") }
      : { tone: "amber" as const, label: tr("validation.conclusion.spaCannotClaim") };
  }
  return row.passed
    ? { tone: "green" as const, label: tr("validation.status.passed") }
    : { tone: "amber" as const, label: tr("validation.status.notPassed") };
}
