"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Check, SlidersHorizontal, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Disclosure } from "@/components/ui/disclosure";
import { compileTrend, type TrendRules } from "./guided-strategy";

function rulesFromConfig(config: Record<string, unknown>): TrendRules {
  const signal = config.signal as Record<string, unknown> | undefined;
  const universe = config.universe as Record<string, unknown> | undefined;
  const risk = config.risk as Record<string, unknown> | undefined;
  const execution = config.execution as Record<string, unknown> | undefined;
  return {
    symbol: Array.isArray(universe?.symbols)
      ? String(universe.symbols[0] ?? "SPY")
      : "SPY",
    lookback: Number(signal?.lookback_period ?? 200),
    position: Number(risk?.max_position_pct ?? 1) * 100,
    slippage: Number(execution?.slippage_bps ?? 5),
    hypothesis: String(config.hypothesis ?? ""),
  };
}

export function GuidedBuilder({
  config,
  code,
  onApply,
  onPending,
}: {
  config: Record<string, unknown>;
  code: string;
  onApply: (result: ReturnType<typeof compileTrend>) => void;
  onPending: (pending: boolean) => void;
}) {
  const [rules, setRules] = useState<TrendRules>(() => rulesFromConfig(config));
  const [edited, setEdited] = useState(false);
  const [appliedSnapshot, setAppliedSnapshot] = useState<{
    code: string;
    rules: string;
  } | null>(null);
  const applied =
    appliedSnapshot?.code === code &&
    appliedSnapshot?.rules === JSON.stringify(rules) &&
    !edited;
  useEffect(() => {
    if (!edited) setRules(rulesFromConfig(config));
  }, [config, edited]);
  const [error, setError] = useState("");
  const [replace, setReplace] = useState(false);
  function patch(next: Partial<TrendRules>) {
    setRules((prev) => ({ ...prev, ...next }));
    setEdited(true);
    setAppliedSnapshot(null);
    setError("");
    onPending(true);
  }
  return (
    <section className="overflow-hidden rounded-as border border-as-border bg-as-bg shadow-as">
      <div className="flex items-start justify-between gap-4 border-b border-as-primary/10 bg-[var(--as-brief-bg)] p-6 text-as-text">
        <div>
          <div className="as-brief-muted mb-2 text-[11px] font-medium tracking-widest">
            01 / 规则
          </div>
          <h2 className="text-xl font-semibold">设定交易规则</h2>
        </div>
        <TrendingUp
          className="as-brief-accent mt-1 h-6 w-6 shrink-0"
          aria-hidden="true"
        />
      </div>
      <form
        className="space-y-6 p-6"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            const result = compileTrend(rules);
            onApply(result);
            setAppliedSnapshot({
              code: result.code,
              rules: JSON.stringify(rules),
            });
            setEdited(false);
            onPending(false);
            setReplace(false);
            setError("");
          } catch (err) {
            setError((err as Error).message);
          }
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-sm font-medium">均线趋势</span>
          <span className="text-xs text-as-muted">选择观察周期</span>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-3 [&>button]:p-3 sm:[&>button]:p-4">
          {[
            { days: 200, title: "长期趋势" },
            { days: 100, title: "中期趋势" },
            { days: 50, title: "短期趋势" },
          ].map((preset) => (
            <button
              key={preset.days}
              type="button"
              aria-pressed={rules.lookback === preset.days}
              onClick={() => patch({ lookback: preset.days })}
              className={`min-h-24 rounded-2xl border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-as-primary ${rules.lookback === preset.days ? "border-as-primary/60 bg-as-primary/10" : "border-as-border hover:bg-as-secondary"}`}
            >
              <span className="block text-xs text-as-muted">
                {preset.title}
              </span>
              <span className="mt-2 block text-xl font-medium tabular">
                {preset.days}
                <span className="ml-1 text-xs font-normal text-as-muted">
                  日
                </span>
              </span>
            </button>
          ))}
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <label className="text-sm">
            交易标的
            <Input
              className="mt-2 block w-full"
              value={rules.symbol}
              onChange={(e) => patch({ symbol: e.target.value.toUpperCase() })}
              required
              pattern="[A-Z][A-Z0-9.\-]{0,9}"
            />
            <span className="mt-2 block text-xs text-as-muted">
              美股 / ETF 代码
            </span>
          </label>
          <label className="text-sm">
            持仓比例 <span className="text-as-muted">%</span>
            <Input
              className="mt-2 block w-full"
              type="number"
              min={1}
              max={100}
              required
              value={rules.position}
              onChange={(e) => patch({ position: Number(e.target.value) })}
            />
            <span className="mt-2 block text-xs text-as-muted">
              剩余资金为现金
            </span>
          </label>
        </div>
        <div className="rounded-xl border border-as-primary/15 bg-[var(--as-primary-soft)] p-5">
          <p className="mb-4 text-xs font-medium text-as-muted">
            {applied ? "已应用到当前代码" : "规则预览"}
          </p>
          <div className="space-y-3 text-sm leading-relaxed">
            <p>
              <span className="mr-3 text-as-primary">买入</span>
              {rules.symbol || "标的"} 收盘价高于 {rules.lookback} 日均线 → 持有{" "}
              {rules.position}% 仓位
            </p>
            <p>
              <span className="mr-3 text-as-primary">卖出</span>
              收盘价低于或等于均线 → 全部转为现金
            </p>
            <p>
              <span className="mr-3 text-as-primary">成交</span>
              收盘后确定信号，下一根日 K 线执行
            </p>
          </div>
        </div>
        <Disclosure title="研究备注（可选）">
          <label className="block text-xs">
            研究想法
            <textarea
              className="as-field mt-2 min-h-24 w-full resize-y rounded-xl border bg-white p-3 text-sm"
              value={rules.hypothesis}
              onChange={(event) => patch({ hypothesis: event.target.value })}
              placeholder="记录为什么选择这个交易思路。"
            />
          </label>
          <p className="mt-2 text-xs">
            备注不转换为交易指令；标的需有历史数据，不使用杠杆。
          </p>
        </Disclosure>
        <details className="group rounded-xl border border-as-border p-4">
          <summary className="flex min-h-6 cursor-pointer items-center gap-2 text-sm font-medium">
            <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
            精细调整与交易成本
          </summary>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="text-sm">
              均线周期（交易日）
              <Input
                className="mt-2 block w-full"
                type="number"
                min={20}
                max={500}
                required
                value={rules.lookback}
                onChange={(e) => patch({ lookback: Number(e.target.value) })}
              />
            </label>
            <label className="text-sm">
              滑点（bps）
              <Input
                className="mt-2 block w-full"
                type="number"
                min={0}
                max={100}
                step="any"
                required
                value={rules.slippage}
                onChange={(e) => patch({ slippage: Number(e.target.value) })}
              />
            </label>
            <p className="text-xs leading-relaxed text-as-muted sm:col-span-2">
              1 bps = 0.01%；另计每笔 1
              美元手续费。修改成本不会自动寻找最优参数。
            </p>
          </div>
        </details>
        <div className="space-y-3 border-t border-as-border pt-5">
          <label className="flex items-start gap-3 text-xs leading-relaxed text-as-muted">
            <input
              className="mt-0.5 h-5 w-5 shrink-0 accent-as-primary"
              type="checkbox"
              checked={replace}
              onChange={(e) => setReplace(e.target.checked)}
            />
            将当前代码替换为以上均线规则。自定义逻辑不会保留；已保存版本可从专业模式恢复。
          </label>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span role="status" className="text-xs text-as-muted">
              {applied
                ? "规则和代码已同步。下一步：设置实验。"
                : "应用规则后，运行实验会自动保存版本。"}
            </span>
            <Button type="submit" disabled={!replace}>
              {applied ? (
                <Check className="h-4 w-4" />
              ) : (
                <ArrowRight className="h-4 w-4" />
              )}
              应用规则到代码
            </Button>
          </div>
          {error && (
            <p role="alert" className="text-sm text-as-negative">
              {error}
            </p>
          )}
        </div>
      </form>
    </section>
  );
}
