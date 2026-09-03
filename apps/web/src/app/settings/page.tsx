"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type IngestJob } from "@/lib/api";
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
  const [job, setJob] = useState<IngestJob | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const status = useQuery({ queryKey: ["data-status"], queryFn: api.dataStatus });

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  const watchJob = (created: IngestJob, doneOk: string) => {
    setJob(created);
    sourceRef.current?.close();
    const es = new EventSource(api.ingestEventsUrl(created.id));
    sourceRef.current = es;
    es.addEventListener("progress", (ev) => {
      try {
        setJob(JSON.parse((ev as MessageEvent).data) as IngestJob);
      } catch {
        /* ignore malformed frames */
      }
    });
    es.addEventListener("done", (ev) => {
      try {
        const finalJob = JSON.parse((ev as MessageEvent).data) as IngestJob;
        setJob(finalJob);
        qc.invalidateQueries({ queryKey: ["data-status"] });
        if (finalJob.status === "COMPLETED") {
          toast(doneOk, "ok");
        } else {
          toast(finalJob.error?.message || "行情任务失败", "err");
        }
      } catch {
        toast("行情任务结束，但无法解析结果", "err");
      } finally {
        es.close();
        sourceRef.current = null;
      }
    });
    es.onerror = () => {
      /* EventSource retries; terminal state arrives via done */
    };
  };

  const ingest = useMutation({
    mutationFn: () => {
      const symbols = tickers
        .split(/[,;\s]+/)
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);
      return api.ingest({ provider: "auto", start: "2010-01-01", symbols });
    },
    onSuccess: (created) => {
      const names = (created.symbols || []).join(", ") || "行情";
      watchJob(created, `${names} 行情已更新`);
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const reconcile = useMutation({
    mutationFn: () => api.reconcileMarket(false),
    onSuccess: (body) => {
      watchJob(body.job, "全量校验完成（新旧快照均保留）");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const running =
    ingest.isPending ||
    reconcile.isPending ||
    (job != null && !["COMPLETED", "FAILED", "CANCELLED"].includes(job.status));
  const cadence = formatReconcileCadence(status.data?.market_reconcile);

  const m = status.data?.manifest || {};
  const lean = status.data?.lean_engine;
  const symbolsLabel = (status.data?.symbols || []).join(", ") || String(m.symbol || "—");

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="设置"
        description="本地单用户工作区。有 POLYGON_API_KEY 时默认 Polygon 主源并对账 yfinance；否则走 Yahoo Finance。不支持分红的数据源（如 Stooq）会拒绝调整价回测，不会静默降级。"
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
            <Row
              label="默认主源"
              value={String((status.data?.providers as { active?: string } | undefined)?.active || "—")}
            />
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
            <Row label="全量校验" value={cadence} />
            <Row label="吞吐" value={formatIngestLimits(status.data?.ingest_limits)} />
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
          <ReconcileReports
            reports={status.data?.reconcile_reports}
            source={status.data?.reconcile_with}
            ready={Boolean(status.data?.ready)}
          />
          <InferredDelistings rows={status.data?.inferred_delistings} ready={Boolean(status.data?.ready)} />
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
              <Button size="sm" onClick={() => ingest.mutate()} disabled={running}>
                {running ? "正在拉取…" : "拉取行情"}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => reconcile.mutate()}
                disabled={running || !status.data?.ready}
                aria-label="对当前标的池做一次全量再拉，检测 vendor 改历史"
              >
                立即全量校验
              </Button>
            </div>
            {running && job ? (
              <div className="rounded-as border border-as-border bg-as-secondary/60 px-3 py-2 text-[11px] text-as-muted">
                <div className="flex items-center justify-between gap-3 text-as-text">
                  <span className="font-medium">{job.progress_step || "排队中"}</span>
                  <span className="tabular-nums">
                    {job.completed_symbols}/{job.total_symbols || "—"}
                  </span>
                </div>
                {job.current_symbol ? (
                  <p className="mt-1">当前标的 {job.current_symbol}</p>
                ) : (
                  <p className="mt-1">任务在 worker 中执行，完成后自动刷新数据状态。</p>
                )}
              </div>
            ) : (
              <p className="text-[11px] text-as-muted">
                每次拉取写入新的不可变快照，不会覆盖旧数据。全量校验按当前标的池再拉一遍，用来发现 vendor 改历史。一次最多 500 只（可调 STREET_INGEST_MAX_SYMBOLS）。
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
            有 <code className="text-as-text">POLYGON_API_KEY</code> 时默认 Polygon
            主源，并对账 yfinance。没有 key 时仍走 Yahoo。市值/行业来自摄取时的基本面快照，不会用今天的市值回填历史。
          </p>
          <ul className="mt-4 space-y-2 text-xs text-as-muted">
            <li>
              <span className="text-as-text">POLYGON_API_KEY</span> — 有 key 即为默认主源（对账 yfinance）
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

function ReconcileReports({
  reports,
  source,
  ready,
}: {
  reports?: Array<{
    symbol?: string;
    primary_source?: string;
    secondary_source?: string;
    compared_bars?: number;
    suspect_bars?: number;
    issues?: Array<{ rule: string; severity: string; message: string; examples?: string[] }>;
  }>;
  source?: string | null;
  ready: boolean;
}) {
  const hasReports = Boolean(reports && reports.length > 0);
  if (!hasReports && !ready) return null;
  if (!hasReports) {
    return (
      <p className="mt-3 text-[11px] text-as-muted">
        尚未做双源对账。有 POLYGON_API_KEY 时默认会对账 yfinance；也可在摄取时指定 reconcile_with。close 偏差超过 10 bps 的 bar 会列在这里。
      </p>
    );
  }
  return (
    <div className="mt-4 rounded-as border border-as-border bg-as-secondary px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-as-text">
        双源对账{source ? `（对账源 ${source}）` : ""}
      </div>
      <ul className="space-y-2 text-as-muted">
        {(reports || []).map((row, index) => (
          <li key={`${row.symbol || "row"}-${index}`}>
            <span className="text-as-text tabular-nums">
              {row.symbol || "—"} · 对比 {row.compared_bars ?? 0} 根 · 可疑 {row.suspect_bars ?? 0} 根
            </span>
            {(row.issues || []).map((issue) => (
              <p key={`${issue.rule}-${issue.severity}`} className="mt-0.5">
                {issue.severity === "blocking" ? "阻断" : "警告"} · {issue.message}
                {issue.examples && issue.examples.length > 0 ? `（${issue.examples[0]}）` : ""}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}

function InferredDelistings({
  rows,
  ready,
}: {
  rows?: Array<{ symbol: string; last_bar: string; effective_to: string }>;
  ready: boolean;
}) {
  if (!ready) return null;
  if (!rows || rows.length === 0) {
    return (
      <p className="mt-3 text-[11px] text-as-muted">
        最近一次摄取没有发现退市（最后一根 K 线仍在 14 个自然日内）。开放区间的成分可在「标的池」按行情关闭。
      </p>
    );
  }
  return (
    <div className="mt-4 rounded-as border border-as-border bg-as-secondary px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-as-text">推断退市</div>
      <ul className="space-y-1 text-as-muted">
        {rows.map((row) => (
          <li key={row.symbol} className="tabular-nums">
            <span className="text-as-text">{row.symbol}</span>
            {" — 最后一根 "}
            {row.last_bar}
            {" → effective_to "}
            {row.effective_to}
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatIngestLimits(cfg?: {
  max_symbols: number;
  rps: number;
  concurrency: number;
} | null): string {
  if (!cfg) return "—";
  const cap = cfg.max_symbols > 0 ? `上限 ${cfg.max_symbols} 标的` : "无上限";
  const rps = cfg.rps > 0 ? `${cfg.rps} 次/秒` : "不限速";
  return `${cap} · ${rps} · 并发 ${cfg.concurrency}`;
}

function formatReconcileCadence(cfg?: {
  enabled: boolean;
  interval_seconds: number;
} | null): string {
  if (!cfg) return "—";
  if (!cfg.enabled) return "定时已关闭（仍可手动）";
  const seconds = cfg.interval_seconds;
  if (seconds % 86_400 === 0) {
    const days = seconds / 86_400;
    return days === 1 ? "每天自动全量再拉" : `每 ${days} 天自动全量再拉`;
  }
  if (seconds % 3_600 === 0) {
    return `每 ${seconds / 3_600} 小时自动全量再拉`;
  }
  return `每 ${seconds} 秒自动全量再拉`;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-as-muted">{label}</dt>
      <dd className="text-right text-as-text">{value}</dd>
    </div>
  );
}
