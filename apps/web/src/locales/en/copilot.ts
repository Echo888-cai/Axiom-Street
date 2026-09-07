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
  insight: {
    title: "Copilot assessment",
    boundary:
      "Aggregate statistics only — strategy source, parameters and market data never leave this platform",
    disabled:
      "Model assessment is disabled: once an API key is configured server-side, Copilot honestly judges from the trial ledger and gate results whether to stop",
    idle:
      "No assessment yet. Copilot judges from the trial ledger and gate results: should you stop?",
    evaluate: "Ask Copilot to assess",
    reevaluate: "Assess again",
    evaluating: "Assessing — usually a few seconds…",
    retry: "Retry",
    failed: "This assessment failed",
    retryHint: "Retry once; repeated failures usually mean a model-service or account problem",
    model: "Model",
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
