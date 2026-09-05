"use client";

import { Modal } from "./modal";
import { Button } from "./button";

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "确认",
  cancelLabel = "取消",
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
          {cancelLabel}
        </Button>
        <Button
          variant={danger ? "danger" : "primary"}
          size="sm"
          onClick={() => {
            onConfirm();
            onClose();
          }}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
