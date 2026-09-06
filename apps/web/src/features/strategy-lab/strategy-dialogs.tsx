"use client";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useT } from "@/lib/i18n";

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
  const t = useT();
  return (
    <>
      <ConfirmDialog
        open={restore != null}
        title={
          restore === "equal"
            ? t("strategy.restoreEqualTitle")
            : t("strategy.restoreSpyTitle")
        }
        description={t("strategy.restoreDescription")}
        confirmLabel={t("strategy.loadTemplateConfirm")}
        onConfirm={() => {
          if (restore) onConfirmRestore(restore);
        }}
        onClose={onCloseRestore}
      />
      <ConfirmDialog
        open={deleteOpen}
        title={t("strategy.deleteStrategyTitle")}
        description={t("strategy.deleteStrategyDescription")}
        confirmLabel={t("strategy.deleteStrategyConfirm")}
        danger
        onConfirm={onConfirmDelete}
        onClose={onCloseDelete}
      />
    </>
  );
}
