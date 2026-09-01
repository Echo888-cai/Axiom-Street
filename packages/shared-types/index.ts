/** Shared DTOs mirrored from FastAPI OpenAPI (Phase 1 hand-maintained). */

export type StrategyStatus =
  | "DRAFT"
  | "BACKTESTED"
  | "VALIDATED"
  | "PAPER"
  | "APPROVED"
  | "LIVE"
  | "PAUSED"
  | "ARCHIVED";

export type BacktestStatus =
  | "QUEUED"
  | "STARTING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface StrategyDTO {
  id: string;
  name: string;
  description: string | null;
  status: StrategyStatus;
  asset_class: string;
  benchmark: string;
}

export interface BacktestDTO {
  id: string;
  strategy_version_id: string;
  start_date: string;
  end_date: string;
  status: BacktestStatus;
  engine_version: string | null;
  data_version: string | null;
}
