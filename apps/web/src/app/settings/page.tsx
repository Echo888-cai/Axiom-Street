"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { toast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const qc = useQueryClient();
  const [tickers, setTickers] = useState("SPY");
  const status = useQuery({ queryKey: ["data-status"], queryFn: api.dataStatus });
  const ingest = useMutation({
    mutationFn: () => {
      const symbols = tickers
        .split(/[,;\s]+/)
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);
      return api.ingest({ provider: "auto", start: "2010-01-01", symbols });
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["data-status"] });
      const names = (result.symbols || []).join(", ") || tickers.toUpperCase();
      toast(`${names} 行情已更新`, "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const m = status.data?.manifest || {};
  const lean = status.data?.lean_engine;
  const symbolsLabel = (status.data?.symbols || []).join(", ") || String(m.symbol || "—");

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="设置"
        description="本地单用户工作区。行情默认走 Yahoo Finance。不支持分红的数据源（如 Stooq）会拒绝调整价回测，不会静默降级。"
      />

      <div className="grid gap-4 md:grid-cols-2 as-stagger">
        <Card>
          <CardHeader title="运行环境" />
          <dl className="space-y-3 text-sm">
            <Row label="API" value={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} />
            <Row label="登录" value="本地用户（无需登录）" />
            <Row label="量化引擎" value="LEAN（Docker / Colima）" />
          </dl>
        </Card>

        <Card>
          <CardHeader
            title="行情数据"
            action={
              status.data?.ready ? <Badge tone="green">已就绪</Badge> : <Badge tone="amber">缺失</Badge>
            }
          />
          <dl className="space-y-3 text-sm">
            <Row label="标的" value={symbolsLabel} />
            <Row label="数据源" value={String(m.source || "—")} />
            <Row label="K 线数量" value={String(m.rows ?? "—")} />
            <Row
              label="区间"
              value={`${m.start ? String(m.start).slice(0, 10) : "—"} → ${m.end ? String(m.end).slice(0, 10) : "—"}`}
            />
            <div className="flex items-center justify-between gap-4">
              <dt className="text-as-muted">SHA256</dt>
              <dd className="flex items-center gap-2 text-xs tabular text-as-muted">
                {m.sha256 ? `${String(m.sha256).slice(0, 12)}…` : "—"}
                {m.sha256 ? (
                  <button
                    type="button"
                    className="cursor-pointer text-as-primary"
                    onClick={() => {
                      navigator.clipboard.writeText(String(m.sha256));
                      toast("已复制指纹", "ok");
                    }}
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </dd>
            </div>
            <Row label="快照" value={String(status.data?.snapshot_key || m.snapshot_key || "—")} />
            <Row
              label="分红/拆分"
              value={
                status.data?.corporate_actions_verified === true || m.corporate_actions_verified === true
                  ? "已核验"
                  : status.data?.corporate_actions_verified === false || m.corporate_actions_verified === false
                    ? "未核验（不可做调整价）"
                    : "—"
              }
            />
            <Row label="LEAN 数据" value={status.data?.lean_ready ? "已转换" : "未转换"} />
          </dl>
          {status.data?.quality_report?.issues && status.data.quality_report.issues.length > 0 ? (
            <div className="mt-4 rounded-as border border-as-border bg-as-secondary px-3 py-2 text-xs">
              <div className="mb-1 font-medium text-as-text">数据质量</div>
              <ul className="space-y-1 text-as-muted">
                {status.data.quality_report.issues.map((issue) => (
                  <li key={`${issue.rule}-${issue.severity}`}>
                    <span className={issue.severity === "blocking" ? "text-as-negative" : ""}>
                      {issue.severity === "blocking" ? "阻断" : "警告"} · {issue.rule}
                    </span>
                    {" — "}
                    {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : status.data?.ready ? (
            <p className="mt-4 text-xs text-as-muted">质量校验通过，无阻断问题。</p>
          ) : null}
          <div className="mt-5 space-y-2">
            <label className="block text-xs text-as-muted" htmlFor="ingest-symbols">
              标的（逗号分隔）
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                id="ingest-symbols"
                value={tickers}
                onChange={(e) => setTickers(e.target.value)}
                placeholder="SPY, QQQ"
                aria-label="要拉取的标的代码"
                className="max-w-[220px]"
              />
              <Button size="sm" onClick={() => ingest.mutate()} disabled={ingest.isPending}>
                {ingest.isPending ? "正在拉取…" : "拉取行情"}
              </Button>
            </div>
            {ingest.isPending ? (
              <p className="text-[11px] text-as-muted">正在下载并转换日线数据，通常需要几秒到几十秒。</p>
            ) : (
              <p className="text-[11px] text-as-muted">
                每次拉取写入新的不可变快照，不会覆盖旧数据。多标的请一次填齐，例如 SPY, QQQ。
              </p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="LEAN / Docker" />
          <dl className="space-y-3 text-sm">
            <Row label="镜像" value={String(lean?.image || "—")} />
            <Row
              label="探活来源"
              value={lean?.source === "worker" ? "Worker" : lean?.source === "api" ? "API 本地" : "—"}
            />
            <div className="flex items-center justify-between gap-4">
              <dt className="text-as-muted">Docker</dt>
              <dd className="flex items-center gap-2">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    lean?.docker_available ? "bg-as-positive as-live-dot" : "bg-as-negative",
                  )}
                />
                {lean?.docker_available ? (
                  <Badge tone="green">可用</Badge>
                ) : (
                  <Badge tone="red">未就绪</Badge>
                )}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-as-muted">
            {lean?.note ||
              "真实回测由 worker 通过 Docker 运行 LEAN。本机可用 Colima 替代 Docker Desktop。"}
          </p>
        </Card>

        <Card>
          <CardHeader title="API Key（可选，后续）" />
          <p className="text-sm leading-relaxed text-as-muted">
            当前不需要 Key。Polygon 双源对账与模拟交易会在后续阶段接入，届时写入{" "}
            <code className="text-as-text">.env</code>。
          </p>
          <ul className="mt-4 space-y-2 text-xs text-as-muted">
            <li>
              <span className="text-as-text">POLYGON_API_KEY</span> — Polygon 美股（Phase 2）
            </li>
            <li>
              <span className="text-as-text">ALPACA_API_KEY</span> +{" "}
              <span className="text-as-text">ALPACA_API_SECRET</span> — 行情与模拟盘
            </li>
            <li>
              <span className="text-as-text">ALPHA_VANTAGE_API_KEY</span>
            </li>
            <li>
              <span className="text-as-text">TIINGO_API_KEY</span>
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-as-muted">{label}</dt>
      <dd className="text-right text-as-text">{value}</dd>
    </div>
  );
}
