"use client";

import { Modal } from "./modal";
import { Button } from "./button";
import { useT } from "@/lib/i18n";

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  danger,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const t = useT();
  const resolvedConfirm = confirmLabel ?? t("common.confirm");
  const resolvedCancel = cancelLabel ?? t("common.cancel");
  if (!open) return null;
  return (
    <Modal open={open} onClose={onClose} label={title} className="max-w-sm p-6">
      <h2 className="text-base font-semibold tracking-tight text-as-text">
        {title}
      </h2>
      {description ? (
        <p className="mt-2 text-sm leading-relaxed text-as-muted">
          {description}
        </p>
      ) : null}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onClose}>
          {resolvedCancel}
        </Button>
        <Button
          variant={danger ? "danger" : "primary"}
          size="sm"
          onClick={() => {
            onConfirm();
            onClose();
          }}
        >
          {resolvedConfirm}
        </Button>
      </div>
    </Modal>
  );
}
