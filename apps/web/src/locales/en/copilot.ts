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
  suggestions: {
    title: "Suggested actions",
    empty: "No suggested actions right now",
    failed: "Could not load suggested actions",
    adopt: "Adopt",
    submitting: "Submitting…",
    queued: "Validation submitted — gate results will flow back here when done",
    reason: {
      never_run: "This gate has never run on the latest version",
      not_passed: "The latest run did not pass — worth one more full run",
      backtest_first:
        "This version has no completed full-sample backtest yet. Run one first; gate suggestions will then appear.",
      superseded_snapshot:
        "Some trials still sit on a data snapshot superseded by a newer one",
      duplicate_parameters:
        "Duplicated parameter trials exist — more fine-tuning feeds the multiple-testing penalty",
    },
    model: {
      title: "Model priority",
      boundary:
        "The model only picks among the deterministic cards above and explains why — it never proposes an action on its own",
      pick: "Model pick:",
      order: "Ask Copilot to rank",
      ordering: "Ranking — usually a few seconds…",
      idle: "No ranking yet. The model picks one of the deterministic cards and says why.",
      failed: "Ranking failed this time",
    },
    confirm: {
      title: "Adopt this suggestion?",
      note: "runs with spec-default parameters on the latest version",
      version: "version",
      submit: "Submit validation",
    },
  },
  chat: {
    title: "Research chat",
    privacy: "Aggregate facts only · no source, parameters or market data",
    disabled: "Research chat is disabled: configure the model API key server-side",
    empty: "Ask Copilot one focused research question. It answers from the current ledger and validation gates.",
    placeholder: "Ask a research question, e.g. What should I do next?",
    send: "Send",
    sending: "Waiting for answer…",
    queued: "Question queued; assembling the research facts…",
    failed: "This conversation did not complete",
    quickStop: "Should I stop?",
    quickNext: "What next?",
    quickPaper: "Ready for paper trading?",
    quickStopPrompt: "Based on the current trials and validation results, should I stop now?",
    quickNextPrompt: "Based on the current trials and validation results, what should I do next?",
    quickPaperPrompt: "Based on the current trials and validation results, is this strategy ready for paper trading?",
    charCount: "chars",
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
