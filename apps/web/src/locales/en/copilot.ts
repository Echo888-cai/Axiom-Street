export const copilot = {
  title: "Copilot context",
  subtitle: "Read-only facts · AI never changes research state",
  version: "Version",
  trials: {
    title: "Trial ledger",
    total: "Total trials for this strategy",
    section: "Per data snapshot",
    duplicate: "Duplicated parameters",
    superseded: "Superseded by a newer snapshot",
    none: "No trials yet",
  },
  gates: {
    title: "Validation gates",
    passed: "Passed",
    failed: "Failed",
    running: "Running",
    none: "No validation runs yet",
  },
  empty: {
    title: "No research context on this page",
    description:
      "Open a strategy or backtest detail page and this panel shows deterministic facts about it: trial counts per data snapshot, duplicated parameters and the latest gate results. Copilot does not generate strategies and never changes validation state.",
  },
  notFound: {
    title: "Cannot read research context",
    description: "The resource does not exist or was deleted; the panel stays empty.",
  },
} as const;
