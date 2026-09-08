import { common } from "./en/common";
import { copilot } from "./en/copilot";
import { validation } from "./en/validation";
import { strategy } from "./en/strategy";
import { backtest } from "./en/backtest";
import { tearsheet } from "./en/tearsheet";
import { data } from "./en/data";
import { universe } from "./en/universe";
import { settings } from "./en/settings";
import { navigation } from "./en/navigation";
import { nav } from "./en/nav";
import { layout } from "./en/layout";
import { portfolio } from "./en/portfolio";
import { paper } from "./en/paper";
import { risk } from "./en/risk";

export const en = {
  common,
  copilot,
  validation,
  strategy,
  backtest,
  tearsheet,
  data,
  universe,
  settings,
  navigation,
  nav,
  layout,
  portfolio,
  paper,
  risk,
} as const;

export type En = typeof en;
