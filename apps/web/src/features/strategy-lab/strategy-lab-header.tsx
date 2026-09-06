"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import type { Strategy } from "@/lib/api";
import { labelStatus } from "@/lib/labels";

export function StrategyLabHeader({
  strategy,
  strategyId,
  editingName,
  name,
  dirty,
  onNameChange,
  onStartEdit,
  onCommitName,
  onBlurName,
  onDelete,
}: {
  strategy: Strategy;
  strategyId: string;
  editingName: boolean;
  name: string;
  dirty: boolean;
  onNameChange: (v: string) => void;
  onStartEdit: () => void;
  onCommitName: () => void;
  onBlurName: () => void;
  onDelete: () => void;
}) {
  return (
    <PageHeader
      crumbs={[
        { href: "/", label: "首页" },
        { href: "/strategies", label: "策略实验室" },
      ]}
      title={
        editingName ? (
          <form className="flex items-center gap-2" onSubmit={(e) => {
            e.preventDefault();
            onCommitName();
          }}>
            <Input
              autoFocus
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              className="h-10 w-[280px] text-[20px] font-semibold"
              onBlur={onBlurName}
            />
          </form>
        ) : (
          <button
            type="button"
            className="cursor-text rounded-lg text-left hover:bg-as-secondary"
            onClick={onStartEdit}
            title="点击重命名"
          >
            {strategy.name}
          </button>
        )
      }
      description={
        strategy.description || "结构化策略工作区。代码是信号的唯一来源。"
      }
      action={
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge tone="neutral">{labelStatus(strategy.status)}</Badge>
          <Badge tone="blue">v{strategy.latest_version?.version ?? 1}</Badge>
          {dirty ? <Badge tone="amber">未保存</Badge> : null}
          <Link href={`/reports?strategy_id=${strategyId}`}>
            <Button variant="ghost" size="sm">
              研究笔记
            </Button>
          </Link>
          <Button variant="ghost" size="sm" onClick={onDelete}>
            删除
          </Button>
        </div>
      }
    />
  );
}
