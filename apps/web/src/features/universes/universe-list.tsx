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

function splitNames(raw: string): string[] | undefined {
  const items = raw
    .split(/[,，;；]/)
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : undefined;
}

function optionalNumber(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : undefined;
}

export function UniverseList() {
  const router = useRouter();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [minAdv, setMinAdv] = useState("");
  const [minCap, setMinCap] = useState("");
  const [sectors, setSectors] = useState("");
  const [industries, setIndustries] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["universes"],
    queryFn: api.listUniverses,
  });

  const create = useMutation({
    mutationFn: () => {
      const price = optionalNumber(minPrice);
      const adv = optionalNumber(minAdv);
      const cap = optionalNumber(minCap);
      const sectorList = splitNames(sectors);
      const industryList = splitNames(industries);
      const rule = price != null || adv != null || cap != null || sectorList || industryList;
      return api.createUniverse({
        name: name.trim(),
        kind: rule ? "RULE" : "STATIC",
        rules: rule
          ? {
              ...(price != null ? { min_price: price } : {}),
              ...(adv != null ? { min_adv_usd: adv } : {}),
              ...(cap != null ? { min_market_cap_usd: cap } : {}),
              ...(sectorList ? { sectors: sectorList } : {}),
              ...(industryList ? { industries: industryList } : {}),
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
      setMinCap("");
      setSectors("");
      setIndustries("");
      router.push(`/universes/${universe.id}`);
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="标的池"
        description="时点正确的成分列表。可手写区间，或按价格、流动性、市值、行业规则从已摄取行情生成。"
      />

      <Card>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="space-y-1 text-[11px] text-as-muted">
              名称
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：含退市的美股池"
                aria-label="标的池名称"
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              最低收盘价（可选）
              <Input
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
                placeholder="5"
                inputMode="decimal"
                aria-label="最低收盘价"
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              最低 ADV$（可选）
              <Input
                value={minAdv}
                onChange={(e) => setMinAdv(e.target.value)}
                placeholder="1000000"
                inputMode="decimal"
                aria-label="最低日均成交额美元"
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              最低市值$（可选）
              <Input
                value={minCap}
                onChange={(e) => setMinCap(e.target.value)}
                placeholder="2000000000"
                inputMode="decimal"
                aria-label="最低市值美元"
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              板块 sectors（可选）
              <Input
                value={sectors}
                onChange={(e) => setSectors(e.target.value)}
                placeholder="Technology, Health Care"
                aria-label="板块列表"
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              行业 industries（可选）
              <Input
                value={industries}
                onChange={(e) => setIndustries(e.target.value)}
                placeholder="Software"
                aria-label="行业列表"
              />
            </label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-[11px] leading-relaxed text-as-muted">
              留空规则字段则建成静态池。市值用「时点股本 × 当日收盘价」；板块/行业只从分类 as-of
              日起生效，不会用今天的行业回填 2015 年。缺少基本面会直接失败。
            </p>
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {create.isPending ? "创建中…" : "新建标的池"}
            </Button>
          </div>
        </form>
      </Card>

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState title="API 未连接" description="请先启动 FastAPI 服务（端口 8000）。" />
        </Card>
      ) : !data?.length ? (
        <Card className="min-h-[240px]">
          <EmptyState
            icon={Layers}
            title="还没有标的池"
            description="没有成分的区间无法开跑回测。手写每支股票的有效区间，或填写价格/流动性/市值/行业规则。"
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
