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
};
