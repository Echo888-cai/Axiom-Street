"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { toast } from "@/components/ui/toast";
import { useT } from "@/lib/i18n";

export function UniverseDetail({ universeId }: { universeId: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const t = useT();
  const universe = useQuery({
    queryKey: ["universe", universeId],
    queryFn: () => api.getUniverse(universeId),
  });
  const [symbol, setSymbol] = useState("");
  const [from, setFrom] = useState("2010-01-04");
  const [to, setTo] = useState("");
  const [infer, setInfer] = useState(false);
  const [asOf, setAsOf] = useState("2018-03-24");
  const [preview, setPreview] = useState<string[] | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["universe", universeId] });
    qc.invalidateQueries({ queryKey: ["universes"] });
  };

  const add = useMutation({
    mutationFn: () =>
      api.addUniverseMember(universeId, {
        symbol: symbol.trim().toUpperCase(),
        effective_from: from,
        effective_to: infer || !to ? null : to,
        infer_effective_to_from_data: infer,
      }),
    onSuccess: () => {
      invalidate();
      setSymbol("");
      setTo("");
      setInfer(false);
      setPreview(null);
      toast(t("common.universeDetail.addedToast"), "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const removeMember = useMutation({
    mutationFn: (memberId: string) => api.deleteUniverseMember(universeId, memberId),
    onSuccess: () => {
      invalidate();
      setPreview(null);
      toast(t("common.universeDetail.removedToast"), "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const removeUniverse = useMutation({
    mutationFn: () => api.deleteUniverse(universeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["universes"] });
      toast(t("common.universeDetail.deletedToast"), "info");
      router.push("/universes");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const runPreview = useMutation({
    mutationFn: () => api.previewUniverse(universeId, { as_of: asOf }),
    onSuccess: (result) => setPreview(result.symbols),
    onError: (err: Error) => toast(err.message, "err"),
  });

  const rebuild = useMutation({
    mutationFn: () => api.rebuildUniverse(universeId),
    onSuccess: () => {
      invalidate();
      toast(t("common.universeDetail.rebuiltToast"), "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  const syncDelist = useMutation({
    mutationFn: () => api.syncUniverseDelistings(),
    onSuccess: (result) => {
      invalidate();
      const n = result.applied.length;
      if (n === 0 && result.errors.length === 0) {
        toast(t("common.universeDetail.noOpenSpansToast"), "info");
        return;
      }
      if (n > 0) {
        toast(
          t("common.universeDetail.writtenDaysToast")
            .split("{n}")
            .join(String(n)),
          "ok",
        );
      }
      if (result.errors.length > 0) {
        toast(result.errors[0].message, "err");
      }
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  if (universe.isLoading) {
    return <Card className="h-40 animate-pulse bg-as-secondary" />;
  }
  if (universe.error || !universe.data) {
    return (
      <Card>
        <EmptyState
          title={t("common.universeDetail.notFoundTitle")}
          description={t("common.universeDetail.notFoundDesc")}
        />
      </Card>
    );
  }

  const row = universe.data;
  const members = [...row.members].sort((a, b) =>
    a.symbol === b.symbol
      ? a.effective_from.localeCompare(b.effective_from)
      : a.symbol.localeCompare(b.symbol),
  );
  const isRule = row.kind === "RULE";
  const ruleHint = isRule
    ? [
        row.rules?.min_price != null
          ? t("common.universeDetail.minPriceClause")
              .split("{n}")
              .join(String(row.rules.min_price))
          : null,
        row.rules?.min_adv_usd != null
          ? t("common.universeDetail.minAdvClause")
              .split("{n}")
              .join(String(row.rules.min_adv_usd))
          : null,
        row.rules?.min_market_cap_usd != null
          ? t("common.universeDetail.minCapClause")
              .split("{n}")
              .join(String(row.rules.min_market_cap_usd))
          : null,
        row.rules?.sectors?.length
          ? t("common.universeDetail.sectorsClause")
              .split("{v}")
              .join(row.rules.sectors.join("/"))
          : null,
        row.rules?.industries?.length
          ? t("common.universeDetail.industriesClause")
              .split("{v}")
              .join(row.rules.industries.join("/"))
          : null,
        t("common.universeDetail.lookbackClause")
          .split("{n}")
          .join(String(row.rules?.lookback_days ?? 21)),
      ]
        .filter(Boolean)
        .join(" · ")
    : null;

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        crumbs={[
          { href: "/", label: t("navigation.home") },
          { href: "/universes", label: t("universe.title") },
        ]}
        title={row.name}
        description={
          row.description ||
          (isRule
            ? t("common.universeDetail.ruleDescription")
                .split("{hint}")
                .join(ruleHint ?? "")
            : t("common.universeDetail.staticDescription"))
        }
        action={
          <div className="flex items-center gap-2">
            {isRule ? (
              <Button
                variant="secondary"
                onClick={() => rebuild.mutate()}
                disabled={rebuild.isPending}
              >
                {rebuild.isPending
                  ? t("common.universeDetail.rebuilding")
                  : t("universe.rebuild")}
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={() => syncDelist.mutate()}
                disabled={syncDelist.isPending}
              >
                {syncDelist.isPending
                  ? t("common.universeDetail.inferring")
                  : t("common.universeDetail.closeDelisted")}
              </Button>
            )}
            <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
              {t("common.universeDetail.deleteUniverse")}
            </Button>
          </div>
        }
      />

      {isRule ? (
        <Card>
          <p className="text-sm text-as-text">{ruleHint}</p>
          <p className="mt-2 text-xs text-as-muted">
            {t("common.universeDetail.ruleExplain")}
          </p>
        </Card>
      ) : (
      <Card>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (symbol.trim()) add.mutate();
          }}
        >
          <label className="space-y-1 text-[11px] text-as-muted">
            {t("common.universeDetail.symbol")}
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="SPY"
              className="w-28 uppercase"
            />
          </label>
          <label className="space-y-1 text-[11px] text-as-muted">
            {t("common.universeDetail.entryDate")}
            <Input type="date" className="w-[148px]" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="space-y-1 text-[11px] text-as-muted">
            {t("common.universeDetail.exitDate")}
            <Input
              type="date"
              className="w-[148px]"
              value={to}
              disabled={infer}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
          <label className="flex h-9 items-center gap-2 text-xs text-as-muted">
            <input
              type="checkbox"
              className="accent-[var(--as-primary)]"
              checked={infer}
              onChange={(e) => setInfer(e.target.checked)}
            />
            {t("common.universeDetail.inferExitDate")}
          </label>
          <Button type="submit" disabled={add.isPending || !symbol.trim()}>
            {add.isPending ? t("common.universeDetail.adding") : t("common.universeDetail.addMember")}
          </Button>
        </form>
        <p className="mt-3 text-xs text-as-muted">
          {t("common.universeDetail.memberHint")}
        </p>
      </Card>
      )}

      <Card className="p-0">
        <div className="border-b border-as-border px-5 py-3 text-sm font-medium">{t("common.universeDetail.membersHeader")}</div>
        {!members.length ? (
          <EmptyState
            title={t("common.universeDetail.noMembersTitle")}
            description={t("common.universeDetail.noMembersDesc")}
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-as-muted">
              <tr className="border-b border-as-border">
                <th className="px-5 py-2 font-medium">{t("common.universeDetail.symbol")}</th>
                <th className="px-5 py-2 font-medium">{t("common.universeDetail.effectiveRange")}</th>
                <th className="px-5 py-2 font-medium">{t("common.universeDetail.status")}</th>
                <th className="px-5 py-2" />
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.id} className="border-b border-as-border last:border-0">
                  <td className="px-5 py-3 font-medium tabular-nums">{member.symbol}</td>
                  <td className="px-5 py-3 tabular-nums text-as-muted">
                    {member.effective_to
                      ? `${member.effective_from.slice(0, 10)} → ${member.effective_to.slice(0, 10)}`
                      : `${member.effective_from.slice(0, 10)} → ${t("common.universeDetail.stillInPool")}`}
                  </td>
                  <td className="px-5 py-3">
                    {member.effective_to ? (
                      <Badge tone="amber">{t("common.universeDetail.exited")}</Badge>
                    ) : (
                      <Badge tone="green">{t("common.universeDetail.stillInPool")}</Badge>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {isRule ? null : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeMember.mutate(member.id)}
                      disabled={removeMember.isPending}
                    >
                      {t("common.universeDetail.remove")}
                    </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card>
        <div className="mb-3 text-sm font-medium">{t("common.universeDetail.previewHeader")}</div>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            runPreview.mutate();
          }}
        >
          <label className="space-y-1 text-[11px] text-as-muted">
            {t("common.universeDetail.asOfLabel")}
            <Input type="date" className="w-[148px]" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          </label>
          <Button type="submit" variant="secondary" disabled={runPreview.isPending}>
            {runPreview.isPending
              ? t("common.universeDetail.querying")
              : t("common.universeDetail.viewMembers")}
          </Button>
        </form>
        {preview ? (
          <p className="mt-3 text-sm tabular-nums text-as-text">
            {preview.length ? preview.join(", ") : t("common.universeDetail.noMembersOnDate")}
          </p>
        ) : (
          <p className="mt-3 text-xs text-as-muted">
            {t("common.universeDetail.previewHint")}
          </p>
        )}
      </Card>

      <ConfirmDialog
        open={confirmDelete}
        title={t("common.universeDetail.deleteTitle")}
        description={t("common.universeDetail.deleteDesc")}
        confirmLabel={t("common.delete")}
        danger
        onConfirm={() => removeUniverse.mutate()}
        onClose={() => setConfirmDelete(false)}
      />
    </div>
  );
}
