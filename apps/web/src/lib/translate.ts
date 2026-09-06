import { locales, defaultLocale } from "@/locales";

export type { Locale } from "@/locales";

let currentLocale = defaultLocale;

export function setLocale(locale: typeof defaultLocale) {
  currentLocale = locale;
}

export function getLocale(): typeof defaultLocale {
  return currentLocale;
}

/** Synchronous lookup for non-React code (libs/utils/errors). Returns the key
 * itself when the path is missing so callers never throw. */
export function tr(key: string): string {
  const t: unknown = locales[currentLocale];
  const keys = key.split(".");
  let value: unknown = t;
  for (const k of keys) {
    if (value && typeof value === "object" && k in value) {
      value = (value as Record<string, unknown>)[k];
    } else {
      return key;
    }
  }
  return typeof value === "string" ? value : key;
}
