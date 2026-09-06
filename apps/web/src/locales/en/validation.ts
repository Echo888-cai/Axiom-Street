export const validation = {
    title: "Validation",
    subtitle:
      "Launch validation tasks. Strategy enters VALIDATED only after all gates pass.",
    kinds: {
      walk_forward: "Walk-Forward",
      dsr: "Deflated Sharpe Ratio",
      pbo: "PBO (Overfitting Probability)",
      sensitivity: "Parameter Sensitivity (Plateau vs Knife-edge)",
      cost: "Cost Sensitivity (Breakeven Slippage)",
      bootstrap: "Stationary Bootstrap CI",
      regime: "Regime Stability",
      spa: "Hansen SPA (Multiple Testing)",
    },
    descriptions: {
      walk_forward:
        "Rolling train/test folds; scoring uses concatenated OOS Sharpe; IS > 0.5 and OOS < 0 = collapse",
      dsr: "Multiple-testing & non-normality correction from trial ledger; ≥ 95% passes",
      pbo: "Combinatorially Symmetric Cross-Validation (CSCV); PBO ≤ 0.5 passes",
      sensitivity:
        "Parameter grid perturbation; ≥3 consecutive points within 0.5 Sharpe bandwidth of peak = plateau",
      cost: "All one-way cost into slippage; linear interp of alpha_capm for breakeven; breakeven > real cost (5 bps) passes",
      bootstrap:
        "Politis-Romano geometric blocks + Politis-White AR(1) block length; Sharpe 95% lower bound > 0 passes; < 252 trading days fails",
      regime:
        "Bull/bear = benchmark 20% peak-valley; high/low vol = 21-day realized vol vs median; rates = FOMC effective dates; each axis ≥ 60 days; complementary regime Sharpe ≥ 0 passes",
      spa: "Hansen SPA_c gate: p < 0.05 and T > 0; also reports White RC / SPA_l / SPA_u; ≥2 distinguishable trials + 252 common days; >64 trials truncated",
    },
    form: {
      kindLabel: "Validation Type",
      strategyVersionIdLabel: "Strategy Version",
      backtestIdLabel: "Backtest (optional)",
      paramsLabel: "Parameters",
      startDateLabel: "Start Date",
      endDateLabel: "End Date",
      trainYearsLabel: "Train Years",
      testYearsLabel: "Test Years",
      modeLabel: "Mode",
      embargoDaysLabel: "Embargo Days",
      valuesLabel: "Parameter Values",
      parameterKeyLabel: "Parameter Key",
      costsBpsLabel: "Cost Grid",
      realisticOneWayBpsLabel: "Realistic One-Way Cost",
      nBootLabel: "Bootstrap Samples",
      confidenceLevelLabel: "Confidence Level",
      methodLabel: "Method",
      meanBlockLengthLabel: "Mean Block Length",
      seedLabel: "Random Seed",
      submit: "Launch Validation",
      submitting: "Submitting...",
      success: "Validation task queued",
      error: "Submission failed",
      helpText: {
        walkForward:
          "Need ≥2 complete OOS folds. Shorter train/test years and longer history = more folds.",
        pbo: "Strategy must read LEAN param lookback. Scan 2-12 distinct positive integers.",
        sensitivity:
          "Strategy must read LEAN param lookback. Need 3-12 distinct positive integers.",
        cost: "Strategy must read LEAN param slippage_bps. Cost grid must include 0 bps.",
        bootstrap:
          "Only stationary / block methods supported. iid resampling rejected.",
        regime:
          "No extra params. Slices completed backtest equity by market regimes.",
        spa: "Uses trial ledger of same family & snapshot in-sample backtests. Needs ≥2 distinguishable trials + 252 common days.",
      },
    },
    status: {
      queued: "Queued",
      running: "Running",
      completed: "Completed",
      failed: "Failed",
      passed: "Passed",
      notPassed: "Not Passed",
    },
    gates: {
      title: "VALIDATED Gate Requirements",
      note: "VALIDATED is system-held: Walk-forward passes, same-version DSR ≥ 95%, param scan PBO ≤ 0.5, sensitivity = plateau not knife-edge, breakeven cost > real cost, Sharpe stationary bootstrap lower bound > 0, bull/bear & high/low vol & rate regimes all non-collapsed, and Hansen SPA_c rejects 'no model beats benchmark' on trial ledger. Client cannot mark strategy as validated.",
      list: [
        "Walk-Forward Pass",
        "DSR ≥ 95%",
        "PBO ≤ 0.5",
        "Sensitivity = Plateau",
        "Breakeven Cost > Real Cost",
        "Bootstrap Sharpe Lower Bound > 0",
        "Regime: Complementary Regime Sharpe ≥ 0",
        "SPA_c: p < 0.05 and T > 0",
      ],
    },
    results: {
      passed: "Passed",
      failed: "Failed",
      details: "Details",
      noResults: "No results yet",
    },
  } as const;
