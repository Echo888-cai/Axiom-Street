"use client";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export type RestoreKind = "spy" | "equal" | null;

export function StrategyDialogs({
  restore,
  deleteOpen,
  onCloseRestore,
  onConfirmRestore,
  onCloseDelete,
  onConfirmDelete,
}: {
  restore: RestoreKind;
  deleteOpen: boolean;
  onCloseRestore: () => void;
  onConfirmRestore: (kind: Exclude<RestoreKind, null>) => void;
  onCloseDelete: () => void;
  onConfirmDelete: () => void;
}) {
  return (
    <>
      <ConfirmDialog
        open={restore != null}
        title={
          restore === "equal" ? "加载等权横截面模板？" : "恢复 SPY 200DMA 模板？"
        }
        description="会覆盖编辑器中的当前代码。未保存的修改将丢失，除非你先保存版本。"
        confirmLabel="载入模板"
        onConfirm={() => {
          if (restore) onConfirmRestore(restore);
        }}
        onClose={onCloseRestore}
      />
      <ConfirmDialog
        open={deleteOpen}
        title="删除这条策略？"
        description="删除后无法从界面恢复。相关回测记录仍会保留。"
        confirmLabel="删除策略"
        danger
        onConfirm={onConfirmDelete}
        onClose={onCloseDelete}
      />
    </>
  );
}
