export const portfolio = {
  title: "Portfolio Attribution",
  description:
    "Review portfolio allocations and server-reconstructable single-period Brinson attribution.",
  selectLabel: "Select portfolio",
  emptyTitle: "No portfolios yet",
  emptyDescription:
    "Create a portfolio and configure strategy weights before attribution appears here.",
  loadErrorTitle: "Portfolio data is unavailable",
  loadErrorDescription:
    "The portfolio API could not be read. Check that the backend is running and retry.",
  allocationTitle: "Current allocation",
  strategyPrefix: "Strategy",
  noAllocations: "This portfolio has no strategy allocations yet.",
  attributionTitle: "Latest attribution",
  asOf: "As of",
  portfolioReturn: "Portfolio return",
  benchmarkReturn: "Benchmark return",
  activeReturn: "Active return",
  allocationEffect: "Allocation effect",
  selectionEffect: "Selection effect",
  interactionEffect: "Interaction effect",
  noAttribution: "No attribution records yet; submit strategy and benchmark returns first.",
  factorTitle: "Factor exposure",
  notAvailableBadge: "Not connected",
  factorDescription:
    "Factor exposure is not connected yet. This page only shows reconstructable allocation, selection, and interaction effects; it does not invent factor data.",
} as const;
