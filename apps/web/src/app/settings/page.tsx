"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { toast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["data-status"], queryFn: api.dataStatus });
  const ingest = useMutation({
    mutationFn: () => api.ingestSpy({ provider: "auto", start: "2010-01-01" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["data-status"] });
      toast("SPY 行情已更新", "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const m = status.data?.manifest || {};
  const lean = status.data?.lean_engine;

  return (
    <div className="space-y-6 aq-enter">
      <PageHeader
        title="设置"
        description="本地单用户工作区。当前行情使用 Yahoo Finance，失败时回退 Stooq，无需 API Key。"
      />

      <div className="grid gap-4 md:grid-cols-2 aq-stagger">
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
            <Row label="数据源" value={String(m.source || "—")} />
            <Row label="K 线数量" value={String(m.rows ?? "—")} />
            <Row
              label="区间"
              value={`${m.start ? String(m.start).slice(0, 10) : "—"} → ${m.end ? String(m.end).slice(0, 10) : "—"}`}
            />
            <div className="flex items-center justify-between gap-4">
              <dt className="text-aq-muted">SHA256</dt>
              <dd className="flex items-center gap-2 text-xs tabular text-aq-muted">
                {m.sha256 ? `${String(m.sha256).slice(0, 12)}…` : "—"}
                {m.sha256 ? (
                  <button
                    type="button"
                    className="cursor-pointer text-aq-primary"
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
            <Row label="LEAN 数据" value={status.data?.lean_ready ? "已转换" : "未转换"} />
          </dl>
          <div className="mt-5">
            <Button size="sm" onClick={() => ingest.mutate()} disabled={ingest.isPending}>
              {ingest.isPending ? "正在拉取 SPY…" : "拉取 SPY 行情"}
            </Button>
            {ingest.isPending ? (
              <p className="mt-2 text-[11px] text-aq-muted">正在下载并转换日线数据，通常需要几秒到几十秒。</p>
            ) : null}
          </div>
        </Card>

        <Card>
          <CardHeader title="LEAN / Docker" />
          <dl className="space-y-3 text-sm">
            <Row label="镜像" value={String(lean?.image || "—")} />
            <div className="flex items-center justify-between gap-4">
              <dt className="text-aq-muted">Docker</dt>
              <dd className="flex items-center gap-2">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    lean?.docker_available ? "bg-aq-positive aq-live-dot" : "bg-aq-negative",
                  )}
                />
                {lean?.docker_available ? (
                  <Badge tone="green">可用</Badge>
                ) : (
                  <Badge tone="red">未检测到</Badge>
                )}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-aq-muted">
            真实回测需要 Docker。本机已用 Colima 替代 Docker Desktop。若不可用，请执行{" "}
            <code className="rounded bg-aq-secondary px-1 py-0.5 text-aq-text">colima start</code>
            ，并重启 API。
          </p>
        </Card>

        <Card>
          <CardHeader title="API Key（可选，后续）" />
          <p className="text-sm leading-relaxed text-aq-muted">
            第一阶段不需要 Key。以后要接机构级行情或模拟交易时，写入{" "}
            <code className="text-aq-text">.env</code>。
          </p>
          <ul className="mt-4 space-y-2 text-xs text-aq-muted">
            <li>
              <span className="text-aq-text">POLYGON_API_KEY</span> — Polygon 美股
            </li>
            <li>
              <span className="text-aq-text">ALPACA_API_KEY</span> +{" "}
              <span className="text-aq-text">ALPACA_API_SECRET</span> — 行情与模拟盘
            </li>
            <li>
              <span className="text-aq-text">ALPHA_VANTAGE_API_KEY</span>
            </li>
            <li>
              <span className="text-aq-text">TIINGO_API_KEY</span>
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
      <dt className="text-aq-muted">{label}</dt>
      <dd className="text-right text-aq-text">{value}</dd>
    </div>
  );
}
