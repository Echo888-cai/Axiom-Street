"use client";

import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";

type Config = Record<string, unknown>;

function nested(obj: Config, key: string): Record<string, unknown> {
  return (obj[key] || {}) as Record<string, unknown>;
}

export function BuilderPanel({
  config,
  onChange,
}: {
  config: Config;
  onChange: (next: Config) => void;
}) {
  const t = useT();
  const universe = nested(config, "universe");
  const signal = nested(config, "signal");
  const risk = nested(config, "risk");
  const execution = nested(config, "execution");
  const symbols = Array.isArray(universe.symbols) ? universe.symbols.join(", ") : "SPY";
  const hypothesis = String(config.hypothesis || "");

  function patch(section: string, key: string, value: unknown) {
    onChange({
      ...config,
      [section]: { ...(config[section] as object), [key]: value },
    });
  }

  return (
    <div className="space-y-4 overflow-auto p-4">
      <label className="block">
        <div className="mb-1.5 text-[11px] font-medium text-as-muted">
          {t("strategy.hypothesisLabel")}
        </div>
        <textarea
          value={hypothesis}
          onChange={(e) => onChange({ ...config, hypothesis: e.target.value })}
          rows={4}
          placeholder={t("strategy.hypothesisPlaceholder")}
          className="w-full resize-none rounded-lg border border-as-border bg-as-bg px-3 py-2 text-sm leading-relaxed text-as-text outline-none placeholder:text-as-muted focus:border-as-primary/40 focus-visible:ring-2 focus-visible:ring-as-primary/20"
        />
        <p className="mt-1.5 text-[10px] leading-relaxed text-as-muted">
          {t("strategy.hypothesisHint")}
        </p>
      </label>
      <Field label={t("strategy.symbolsLabel")}>
        <Input
          value={symbols}
          onChange={(e) =>
            patch(
              "universe",
              "symbols",
              e.target.value
                .split(",")
                .map((s) => s.trim().toUpperCase())
                .filter(Boolean),
            )
          }
        />
      </Field>
      {universe.universe_filter === "equal_weight" ? (
        <p className="text-[11px] leading-relaxed text-as-muted">
          {t("strategy.equalWeightNote")}
        </p>
      ) : (
        <>
          <Field
            label={t("strategy.movingAverageLabel")}
            hint={t("strategy.movingAverageHint")}
          >
            <Input
              type="number"
              min={20}
              value={Number(signal.lookback_period || 200)}
              onChange={(e) => patch("signal", "lookback_period", Number(e.target.value) || 200)}
            />
          </Field>
          <p className="text-[11px] leading-relaxed text-as-muted">
            {t("strategy.entrySignalPrefix")}
            {String(signal.entry_signal || "close > SMA")}
            {t("strategy.settlementConvention")}
          </p>
        </>
      )}
      <Field label={t("strategy.slippageLabel")}>
        <Input
          type="number"
          min={0}
          value={Number(execution.slippage_bps ?? 5)}
          onChange={(e) => patch("execution", "slippage_bps", Number(e.target.value) || 0)}
        />
      </Field>
      <Field label={t("strategy.maxPositionLabel")}>
        <Input
          type="number"
          min={1}
          max={100}
          value={Math.round(Number(risk.max_position_pct || 1) * 100)}
          onChange={(e) => patch("risk", "max_position_pct", (Number(e.target.value) || 100) / 100)}
        />
      </Field>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-[11px] font-medium text-as-muted">{label}</span>
        {hint ? <span className="text-[10px] text-as-muted">{hint}</span> : null}
      </div>
      {children}
    </label>
  );
}
