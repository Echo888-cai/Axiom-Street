"use client";

import { Input } from "@/components/ui/input";

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
        <div className="mb-1.5 text-[11px] font-medium text-aq-muted">投资假设</div>
        <textarea
          value={hypothesis}
          onChange={(e) => onChange({ ...config, hypothesis: e.target.value })}
          rows={4}
          placeholder="用一句话写下这条策略为什么应该赚钱。"
          className="w-full resize-none rounded-lg border border-aq-border bg-aq-bg px-3 py-2 text-sm leading-relaxed text-aq-text outline-none placeholder:text-aq-muted focus:border-aq-primary/40 focus:ring-2 focus-visible:ring-aq-primary/20"
        />
      </label>
      <Field label="标的">
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
      <Field label="均线周期" hint="记录假设；实际信号以代码为准">
        <Input
          type="number"
          min={20}
          value={Number(signal.lookback_period || 200)}
          onChange={(e) => patch("signal", "lookback_period", Number(e.target.value) || 200)}
        />
      </Field>
      <Field label="滑点（bps）">
        <Input
          type="number"
          min={0}
          value={Number(execution.slippage_bps || 5)}
          onChange={(e) => patch("execution", "slippage_bps", Number(e.target.value) || 0)}
        />
      </Field>
      <Field label="单票上限 %">
        <Input
          type="number"
          min={1}
          max={100}
          value={Math.round(Number(risk.max_position_pct || 1) * 100)}
          onChange={(e) => patch("risk", "max_position_pct", (Number(e.target.value) || 100) / 100)}
        />
      </Field>
      <p className="text-[11px] leading-relaxed text-aq-muted">
        入场：{String(signal.entry_signal || "close > SMA")}。成交约定为收盘信号、下一根 K 线成交。
      </p>
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
        <span className="text-[11px] font-medium text-aq-muted">{label}</span>
        {hint ? <span className="text-[10px] text-aq-muted">{hint}</span> : null}
      </div>
      {children}
    </label>
  );
}
