import { request } from "./http";
import type {
  PaperOrder,
  PaperOrderAccepted,
  PaperPositions,
  PaperReconciliation,
} from "./types";

export type PaperOrderInput = {
  strategy_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  simulation_price: number;
  client_order_id: string;
};

// P5 持续模拟会话
export type PaperSession = {
  id: string;
  strategy_id: string;
  name: string;
  status: string;
  limits: Record<string, number>;
  account: Record<string, unknown>;
  observation_days: number;
  kill_switch: boolean;
};
export type ObservationStatus = {
  session_id: string;
  observation_days: number;
  observation_target: number;
  sufficient: boolean;
  executed_signals: number;
  note: string;
};

export const paperApi = {
  createOrder: (body: PaperOrderInput) =>
    request<PaperOrderAccepted>("/api/v1/paper/orders", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listOrders: (strategyId: string, limit = 50) =>
    request<PaperOrder[]>(
      `/api/v1/paper/orders?strategy_id=${encodeURIComponent(strategyId)}&limit=${limit}`,
    ),
  getPositions: (strategyId: string) =>
    request<PaperPositions>(
      `/api/v1/paper/positions?strategy_id=${encodeURIComponent(strategyId)}`,
    ),
  getReconciliation: (strategyId: string) =>
    request<PaperReconciliation | null>(
      `/api/v1/paper/reconciliation?strategy_id=${encodeURIComponent(strategyId)}`,
    ),

  // P5 持续模拟会话（市场时钟/观察期）
  createPaperSession: (body: { strategy_id: string; name?: string; initial_cash?: number }) =>
    request<PaperSession>("/api/v1/paper-sessions", {
      method: "POST",
      body: JSON.stringify({ ...body, name: body.name ?? "模拟会话" }),
    }),
  haltPaperSession: (id: string) =>
    request<PaperSession>(`/api/v1/paper-sessions/${id}/halt`, { method: "POST" }),
  resumePaperSession: (id: string) =>
    request<PaperSession>(`/api/v1/paper-sessions/${id}/resume`, { method: "POST" }),
  toggleKillSwitch: (id: string, enabled: boolean) =>
    request<PaperSession>(`/api/v1/paper-sessions/${id}/kill-switch?enabled=${enabled}`, {
      method: "POST",
    }),
  observationStatus: (id: string) =>
    request<ObservationStatus>(`/api/v1/paper-sessions/${id}/observation-status`),
};