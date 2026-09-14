"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import type { FactorRegressionRecord } from "@/lib/api/portfolios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { formatRelative } from "@/lib/utils";

function parseExposures(text: string): Record<string, number> | null {
  try {
    const parsed = JSON.parse(text) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const out: Record<string, number> = {};
      for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
        if (typeof v !== "number" || !Number.isFinite(v)) return null;
        out[k] = v;
      }
      return out;
    }
  } catch {
    return null;
  }
  return null;
}

/** P3.4 因子暴露台账：只展示有记录（模型/来源/频率/窗口齐全）的回归；无数据不虚构。 */
export function FactorExposuresCard({ portfolioId }: { portfolioId: string }) {
  const qc = useQueryClient();
  const [source, setSource] = useState("computed");
  const [frequency, setFrequency] = useState("monthly");
  const [nObs, setNObs] = useState("12");
  const [exposuresText, setExposuresText] = useState('{"market": 0.9}');

  const rows = useQuery({
    queryKey: ["factor-regressions", portfolioId],
    queryFn: () => api.listFactorRegressions(portfolioId),
  });
  const create = useMutation({
    mutationFn: () => {
      const exposures = parseExposures(exposuresText);
      if (!exposures) throw new Error("exposures 需是 {因子: 数值} 的 JSON");
      const n = Number(nObs);
      if (!Number.isFinite(n) || n < 2) throw new Error("至少需要 2 期观察，否则估计只是噪声");
      return api.createFactorRegression(portfolioId, {
        model: "OLS",
        source,
        frequency,
        n_obs: n,
        exposures,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["factor-regressions", portfolioId] });
      toast("已记录因子回归（含来源/频率/窗口）。", "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const list = rows.data ?? [];
  return (
    <section className="rounded-as border border-as-border bg-as-bg p-5 shadow-as">
      <div className="flex items-center gap-2">
        <FlaskConical className="h-4 w-4 text-as-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold">因子暴露台账</h2>
      </div>
      <p className="mt-1 text-[10px] leading-relaxed text-as-muted">
        每一条记录都必须携带模型/来源/频率与观察数；没有任何因子数据时这里保持为空，绝不虚构暴露。
      </p>

      {rows.isLoading ? (
        <p className="mt-3 text-xs text-as-muted">读取中…</p>
      ) : list.length === 0 ? (
        <p className="mt-3 rounded-xl border border-as-border/60 bg-as-secondary/40 px-3 py-4 text-xs text-as-muted">
          暂无因子回归记录。接入因子数据并（在证据充分时）记录回归后才会显示暴露。
        </p>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {list.map((row: FactorRegressionRecord) => (
            <li key={row.id} className="flex flex-wrap items-center gap-2 text-xs">
              <Badge tone="blue">{row.frequency}</Badge>
              <Badge tone="neutral">{row.model}</Badge>
              <span className="text-as-muted">
                {row.source} · R² {row.r2.toFixed(2)} · n={row.n_obs}
              </span>
              <span className="text-as-text">
                {Object.entries(row.exposures)
                  .map(([k, v]) => `${k} ${v >= 0 ? "+" : ""}${v.toFixed(2)}`)
                  .join("，")}
              </span>
              <span className="ml-auto text-[10px] text-as-muted">
                {formatRelative(row.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <form
        className="mt-4 grid gap-3 border-t border-as-border pt-4 sm:grid-cols-2"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        <label className="text-xs text-as-muted">
          来源
          <input
            className="as-field mt-1 w-full rounded-xl border border-as-border bg-white p-2 text-sm"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          />
        </label>
        <label className="text-xs text-as-muted">
          频率
          <select
            className="as-field mt-1 w-full rounded-xl border border-as-border bg-white p-2 text-sm"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
          >
            <option>daily</option>
            <option>weekly</option>
            <option>monthly</option>
          </select>
        </label>
        <label className="text-xs text-as-muted">
          观察期数
          <input
            className="as-field mt-1 w-full rounded-xl border border-as-border bg-white p-2 text-sm"
            type="number"
            min={2}
            value={nObs}
            onChange={(e) => setNObs(e.target.value)}
          />
        </label>
        <label className="text-xs text-as-muted">
          暴露（JSON，如 {"{market: 0.9}"}）
          <input
            className="as-field mt-1 w-full rounded-xl border border-as-border bg-white px-2 py-2 font-mono text-sm"
            value={exposuresText}
            onChange={(e) => setExposuresText(e.target.value)}
          />
        </label>
        <div className="sm:col-span-2">
          <Button type="submit" size="sm" disabled={create.isPending || !portfolioId}>
            {create.isPending ? "记录中…" : "记录回归"}
          </Button>
        </div>
      </form>
    </section>
  );
}