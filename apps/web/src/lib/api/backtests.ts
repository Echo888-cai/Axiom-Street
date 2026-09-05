import { request, API_URL, unwrapList } from "./http";
import type {
  Backtest,
  BacktestMetrics,
  EquityPoint,
  Trade,
  TimeSeriesPoint,
  MonthlyReturn,
  Page,
} from "./types";

export const backtestsApi = {
  listBacktests: (params?: { strategy_id?: string; status?: string }) => {
    const search = new URLSearchParams();
    if (params?.strategy_id) search.set("strategy_id", params.strategy_id);
    if (params?.status) search.set("status", params.status);
    const q = search.toString();
    return request<Page<Backtest> | Backtest[]>(
      `/api/v1/backtests${q ? `?${q}` : ""}`,
    ).then(unwrapList);
  },
  getBacktest: (id: string) => request<Backtest>(`/api/v1/backtests/${id}`),
  cancelBacktest: (id: string) =>
    request<Backtest>(`/api/v1/backtests/${id}/cancel`, { method: "POST" }),
  createBacktest: (body: {
    strategy_version_id: string;
    start_date: string;
    end_date: string;
    benchmark?: string;
    initial_capital?: number;
    data_snapshot_id?: string;
    universe?: string[];
    universe_id?: string;
    force?: boolean;
  }) =>
    request<Backtest>("/api/v1/backtests", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getMetrics: (id: string) =>
    request<BacktestMetrics>(`/api/v1/backtests/${id}/metrics`),
  getEquity: (id: string) =>
    request<Page<EquityPoint> | EquityPoint[]>(
      `/api/v1/backtests/${id}/equity`,
    ).then(unwrapList),
  getTrades: (id: string) =>
    request<Page<Trade> | Trade[]>(`/api/v1/backtests/${id}/trades`).then(
      unwrapList,
    ),
  getMonthlyReturns: (id: string) =>
    request<MonthlyReturn[]>(`/api/v1/backtests/${id}/monthly-returns`),
  getTimeSeries: (id: string, name?: string) => {
    const q = name ? `?name=${encodeURIComponent(name)}` : "";
    return request<TimeSeriesPoint[]>(
      `/api/v1/backtests/${id}/time-series${q}`,
    );
  },
  tearsheetPdfUrl: (id: string) =>
    `${API_URL}/api/v1/backtests/${id}/tearsheet.pdf`,
  tearsheetHtmlUrl: (id: string) =>
    `${API_URL}/api/v1/backtests/${id}/tearsheet.html`,
  eventsUrl: (id: string) => `${API_URL}/api/v1/backtests/${id}/events`,
};
