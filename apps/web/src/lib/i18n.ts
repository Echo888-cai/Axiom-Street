"use client";

import { useSyncExternalStore } from "react";
import { locales, defaultLocale, type ZhCN } from "@/locales";
import { setLocale as storeSetLocale, getLocale, type Locale } from "./translate";

const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

export function setLocale(locale: Locale) {
  storeSetLocale(locale);
  listeners.forEach((listener) => listener());
}

export function useLocale() {
  return useSyncExternalStore(subscribe, getLocale, () => defaultLocale);
}

export function useI18n() {
  const locale = useLocale();
  const t = locales[locale];
  return t as ZhCN;
}

export function useT() {
  const t = useI18n();
  return (key: string) => {
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
  };
}

