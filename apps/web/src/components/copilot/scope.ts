// Right-rail panel page scoping (P5-1): the panel is global, but it only has
// research context when the current route names a strategy or a backtest.
// Lists and unrelated pages intentionally resolve to null (honest empty state).

export type CopilotScope =
  | { resource: "strategy"; id: string }
  | { resource: "backtest"; id: string };

const UUID_PATTERN =
  "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

export function parseScope(pathname: string): CopilotScope | null {
  const strategy = pathname.match(new RegExp(`^/strategies/(${UUID_PATTERN})`));
  if (strategy) return { resource: "strategy", id: strategy[1] };
  const backtest = pathname.match(new RegExp(`^/backtests/(${UUID_PATTERN})`));
  if (backtest) return { resource: "backtest", id: backtest[1] };
  return null;
}
