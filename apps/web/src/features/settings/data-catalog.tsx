"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Database, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { CapabilityProbe } from "@/lib/api/data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { formatRelative } from "@/lib/utils";

/** P3.1 数据目录：来源/覆盖/频率/时区/复权/缺口/授权能力统一查看 + 权限探测。 */
export function DataCatalogCard() {
  const catalog = useQuery({
    queryKey: ["data-catalog"],
    queryFn: api.dataCatalog,
  });
  const probe = useMutation({
    mutationFn: () =>
      api.probeCapabilities({ provider: "polygon", symbol: "SPY" }),
    onSuccess: (result: CapabilityProbe) => {
      const ok = Object.values(result.capabilities).every((c) => c.code === "ok");
      toast(ok ? "数据权限探测通过。" : "数据权限探测完成，存在需要处理的缺口。", ok ? "ok" : "err");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });
  const probeResult = probe.data;

  const rows = catalog.data?.snapshots ?? [];
  const reasons = probeResult?.capabilities
    ? ([
        { key: "price", label: "价格", reason: probeResult.capabilities.price },
        { key: "dividends", label: "分红", reason: probeResult.capabilities.dividends },
        { key: "splits", label: "拆分", reason: probeResult.capabilities.splits },
      ] as const)
    : [];

  return (
    <section className="rounded-as border border-as-border bg-as-bg p-5 shadow-as">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Database className="h-4 w-4 text-as-primary" aria-hidden="true" />
          数据目录
        </h2>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => probe.mutate()}
          disabled={probe.isPending}
        >
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
          {probe.isPending ? "探测中…" : "探测数据权限（polygon）"}
        </Button>
      </div>

      {probeResult ? (
        <ul className="mt-4 space-y-1.5">
          {reasons.map(({ key, label, reason }) => (
            <li key={key} className="flex items-start gap-2 text-xs">
              <Badge tone={reason.code === "ok" ? "green" : "amber"}>{label}</Badge>
              <span className={reason.code === "ok" ? "text-as-positive" : "text-as-muted"}>
                {reason.message}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-[11px] leading-relaxed text-as-muted">
          探测会分别检查价格、分红、拆分的访问权限（401/403/限流/缺数都会给出可行动原因），不写入任何快照。
        </p>
      )}

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-xs">
          <thead>
            <tr className="border-b border-as-border text-as-muted">
              <th className="px-2 py-2 font-medium">快照</th>
              <th className="px-2 py-2 font-medium">来源/区间</th>
              <th className="px-2 py-2 font-medium">频率/时区/复权</th>
              <th className="px-2 py-2 font-medium">分红/拆分</th>
              <th className="px-2 py-2 font-medium">缺口</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-2 py-6 text-center text-as-muted">
                  还没有留存快照。完成一次摄取后会在 snapshots/ 记录快照血缘。
                </td>
              </tr>
            ) : (
              rows.map((snap) => (
                <tr key={snap.snapshot_key} className="border-b border-as-border/60">
                  <td className="px-2 py-2 font-medium">{snap.snapshot_key}</td>
                  <td className="px-2 py-2 text-as-muted">
                    {snap.symbols.join(", ")} · {snap.range.start ?? "?"} →{" "}
                    {snap.range.end ?? "?"}
                  </td>
                  <td className="px-2 py-2 text-as-muted">
                    {snap.frequency} · {snap.timezone} · {snap.adjustment}
                  </td>
                  <td className="px-2 py-2">
                    {snap.corporate_actions_verified ? (
                      <Badge tone="green">已核验</Badge>
                    ) : (
                      <Badge tone="amber">未核验</Badge>
                    )}
                  </td>
                  <td className="px-2 py-2 text-as-muted">
                    {snap.gaps.length ? `${snap.gaps.length} 项` : "无"}
                    {snap.gaps.length ? (
                      <span title={snap.gaps.map((g) => `${g.rule}: ${g.message ?? ""}`).join("；")}>
                        ⚠
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {catalog.data?.snapshots?.[0] ? (
        <p className="mt-3 text-[10px] text-as-muted">
          最新快照 {catalog.data.snapshots[0].snapshot_key} · 更新于{" "}
          {formatRelative(catalog.data.snapshots[0].created_at ?? "")}
        </p>
      ) : null}
    </section>
  );
}