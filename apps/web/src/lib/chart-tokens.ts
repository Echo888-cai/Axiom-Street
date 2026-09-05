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
    return token("--as-primary", "#4167ac");
  },
  get background() {
    return token("--as-bg", "#ffffff");
  },
  get muted() {
    return token("--as-text-secondary", "#737984");
  },
  get positive() {
    return token("--as-positive", "#34806a");
  },
  get negative() {
    return token("--as-negative", "#bb5b62");
  },
  get benchmark() {
    return token("--as-chart-benchmark", "#a4adba");
  },
  get grid() {
    return token("--as-grid", "rgba(34,45,61,.045)");
  },
  get crosshair() {
    return token("--as-chart-crosshair", "rgba(65,103,172,.25)");
  },
  get negativeArea() {
    return token("--as-chart-negative-area", "rgba(187,91,98,.16)");
  },
  get negativeFade() {
    return token("--as-chart-negative-fade", "rgba(187,91,98,.01)");
  },
};
