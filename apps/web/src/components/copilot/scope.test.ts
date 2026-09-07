import { describe, expect, it } from "vitest";
import { parseScope } from "./scope";

const SID = "00000000-0000-4000-8000-000000000001";
const BID = "00000000-0000-4000-8000-000000000002";

describe("parseScope", () => {
  it("maps a strategy detail route to strategy scope", () => {
    expect(parseScope(`/strategies/${SID}`)).toEqual({ resource: "strategy", id: SID });
  });

  it("maps nested strategy child routes to the same strategy scope", () => {
    expect(parseScope(`/strategies/${SID}/backtests`)).toEqual({
      resource: "strategy",
      id: SID,
    });
  });

  it("maps a backtest detail route to backtest scope", () => {
    expect(parseScope(`/backtests/${BID}`)).toEqual({ resource: "backtest", id: BID });
  });

  it("returns null for pages without research context", () => {
    for (const pathname of [
      "/",
      "/strategies",
      "/backtests",
      "/validation",
      "/universes",
      "/settings",
      "/experiments",
    ]) {
      expect(parseScope(pathname)).toBeNull();
    }
  });

  it("returns null for ids that are not uuids", () => {
    expect(parseScope("/strategies/not-a-uuid")).toBeNull();
    expect(parseScope("/backtests/42")).toBeNull();
  });
});
