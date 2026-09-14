import { request } from "./http";

export type TaskKind = "backtest" | "validation" | "ingest" | "copilot";

export interface Task {
  id: string;
  kind: TaskKind;
  title: string;
  status: string;
  progress_step?: string | null;
  created_at: string;
  finished_at?: string | null;
  ref?: string | null;
  strategy_name?: string | null;
  cancelable: boolean;
}

export const tasksApi = {
  // P2.2 统一任务读模型（回测/验证/摄取/研究助手）。
  listTasks: (limit = 50) =>
    request<Task[]>(`/api/v1/tasks?limit=${limit}`),
  getTask: (id: string) => request<Task>(`/api/v1/tasks/${id}`),
  cancelTask: (id: string) =>
    request<Task>(`/api/v1/tasks/${id}/cancel`, { method: "POST" }),
};