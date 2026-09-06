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
import { useT } from "@/lib/i18n";

function splitNames(raw: string): string[] | undefined {
  const items = raw
    .split(/[,;\uFF0C\uFF1B]/)
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
  const t = useT();
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
      toast(t("common.universeList.createdToast"), "ok");
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
        title={t("universe.title")}
        description={t("common.universeList.description")}
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
              {t("common.universeList.name")}
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("common.universeList.namePlaceholder")}
                aria-label={t("common.universeList.nameAria")}
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              {t("common.universeList.minPrice")}
              <Input
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
                placeholder="5"
                inputMode="decimal"
                aria-label={t("common.universeList.minPriceAria")}
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              {t("common.universeList.minAdv")}
              <Input
                value={minAdv}
                onChange={(e) => setMinAdv(e.target.value)}
                placeholder="1000000"
                inputMode="decimal"
                aria-label={t("common.universeList.minAdvAria")}
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              {t("common.universeList.minCap")}
              <Input
                value={minCap}
                onChange={(e) => setMinCap(e.target.value)}
                placeholder="2000000000"
                inputMode="decimal"
                aria-label={t("common.universeList.minCapAria")}
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              {t("common.universeList.sectors")}
              <Input
                value={sectors}
                onChange={(e) => setSectors(e.target.value)}
                placeholder="Technology, Health Care"
                aria-label={t("common.universeList.sectorsAria")}
              />
            </label>
            <label className="space-y-1 text-[11px] text-as-muted">
              {t("common.universeList.industries")}
              <Input
                value={industries}
                onChange={(e) => setIndustries(e.target.value)}
                placeholder="Software"
                aria-label={t("common.universeList.industriesAria")}
              />
            </label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-[11px] leading-relaxed text-as-muted">
              {t("common.universeList.rulesHint")}
            </p>
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {create.isPending ? t("common.creating") : t("universe.new")}
            </Button>
          </div>
        </form>
      </Card>

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState
            title={t("common.universeList.apiNotConnectedTitle")}
            description={t("common.universeList.apiNotConnectedDesc")}
          />
        </Card>
      ) : !data?.length ? (
        <Card className="min-h-[240px]">
          <EmptyState
            icon={Layers}
            title={t("common.universeList.noUniversesTitle")}
            description={t("common.universeList.noUniversesDesc")}
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
                    {item.description || t("common.universeList.noDescription")}
                  </div>
                </div>
                <div className="shrink-0 text-right text-xs text-as-muted">
                  <div className="tabular-nums text-sm text-as-text">
                    {t("common.universeList.membersCount")
                      .split("{n}")
                      .join(String(item.member_count))}
                  </div>
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
