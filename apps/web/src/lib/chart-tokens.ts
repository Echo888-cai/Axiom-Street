/** Canvas charts require resolved colors rather than CSS var() strings. */
function token(name: string, fallback: string): string {
  return typeof document === "undefined"
    ? fallback
    : getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim() || fallback;
}

export const chartColors = {
  get primary() {
    return token("--as-primary", "#1677FF");
  },
  get background() {
    return token("--as-bg", "#FFFFFF");
  },
  get muted() {
    return token("--as-text-muted", "#667085");
  },
  get positive() {
    return token("--as-positive", "#3fa97c");
  },
  get negative() {
    return token("--as-negative", "#d9635e");
  },
  get benchmark() {
    return token("--as-chart-benchmark", "#a4adba");
  },
  get grid() {
    return token("--as-border-subtle", "rgba(15,23,42,0.065)");
  },
  get crosshair() {
    return token("--as-border-strong", "rgba(15,23,42,0.13)");
  },
  get negativeArea() {
    return token("--as-negative", "#d9635e") + "26"; // 15% opacity
  },
  get negativeFade() {
    return token("--as-negative", "#d9635e") + "04"; // 1% opacity
  },
};