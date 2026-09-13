import { common } from "./zh/common";
import { copilot } from "./zh/copilot";
import { validation } from "./zh/validation";
import { strategy } from "./zh/strategy";
import { backtest } from "./zh/backtest";
import { tearsheet } from "./zh/tearsheet";
import { data } from "./zh/data";
import { universe } from "./zh/universe";
import { settings } from "./zh/settings";
import { nav } from "./zh/nav";
import { layout } from "./zh/layout";
import { portfolio } from "./zh/portfolio";
import { paper } from "./zh/paper";
import { risk } from "./zh/risk";

export const zhCN = {
  common,
  copilot,
  validation,
  strategy,
  backtest,
  tearsheet,
  data,
  universe,
  settings,
  nav,
  layout,
  portfolio,
  paper,
  risk,
} as const;

export type ZhCN = typeof zhCN;
