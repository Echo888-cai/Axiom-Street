import { zhCN } from "./zh-CN";
import { en } from "./en";

export { zhCN, type ZhCN } from "./zh-CN";
export { en, type En } from "./en";

export type Locale = "zh-CN" | "en";

export const defaultLocale: Locale = "zh-CN";

export const locales = {
  "zh-CN": zhCN,
  en: en,
} as const;
