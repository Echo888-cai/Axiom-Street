"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Layers } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { toast } from "@/components/ui/toast";
import { formatRelative } from "@/lib/utils";

export function UniverseList() {
  const router = useRouter();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [minAdv, setMinAdv] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["universes"],
    queryFn: api.listUniverses,
  });

  const create = useMutation({
    mutationFn: () => {
      const price = minPrice.trim() ? Number(minPrice) : undefined;
      const adv = minAdv.trim() ? Number(minAdv) : undefined;
      const rule = price != null || adv != null;
      return api.createUniverse({
        name: name.trim(),
        kind: rule ? "RULE" : "STATIC",
        rules: rule
          ? {
              ...(price != null ? { min_price: price } : {}),
              ...(adv != null ? { min_adv_usd: adv } : {}),
            }
          : undefined,
      });
    },
    onSuccess: (universe) => {
      qc.invalidateQueries({ queryKey: ["universes"] });
      toast("标的池已创建", "ok");
      setName("");
      setMinPrice("");
      setMinAdv("");
      router.push(`/universes/${universe.id}`);
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="标的池"
        description="时点正确的成分列表。可手写区间，或按价格/流动性规则从已摄取行情生成。"
        action={
          <form
            className="flex flex-wrap items-center justify-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) create.mutate();
            }}
          >
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：含退市的美股池"
              className="w-44"
            />
            <Input
              value={minPrice}
              onChange={(e) => setMinPrice(e.target.value)}
              placeholder="最低价（可选）"
              inputMode="decimal"
              className="w-28"
              aria-label="最低收盘价"
            />
            <Input
              value={minAdv}
              onChange={(e) => setMinAdv(e.target.value)}
              placeholder="最低 ADV$（可选）"
              inputMode="decimal"
              className="w-36"
              aria-label="最低日均成交额美元"
            />
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {create.isPending ? "创建中…" : "新建标的池"}
            </Button>
          </form>
        }
      />

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState title="API 未连接" description="请先启动 FastAPI 服务（端口 8000）。" />
        </Card>
      ) : !data?.length ? (
        <Card className="min-h-[320px]">
          <EmptyState
            icon={Layers}
            title="还没有标的池"
            description="没有成分的区间无法开跑回测。手写每支股票的有效区间，或填写最低价/ADV 建成规则池。"
          />
        </Card>
      ) : (
        <div className="grid gap-3 as-stagger">
          {data.map((item) => (
            <Link key={item.id} href={`/universes/${item.id}`}>
              <Card hover className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-medium text-as-text">{item.name}</div>
                    <Badge tone="blue">{item.kind}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-as-muted">
                    {item.description || "暂无描述"}
                  </div>
                </div>
                <div className="shrink-0 text-right text-xs text-as-muted">
                  <div className="tabular-nums text-sm text-as-text">{item.member_count} 支</div>
                  <div>{formatRelative(item.updated_at)}</div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
