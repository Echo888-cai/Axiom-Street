"use client";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

/** Native top-layer modal: focus containment, Escape and focus restoration. */
export function Modal({
  open,
  onClose,
  label,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (open) dialog?.showModal();
    else dialog?.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-label={label}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === ref.current) {
          const rect = ref.current!.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            onClose();
        }
      }}
      className={cn(
        "as-glass m-auto max-h-[85dvh] w-[calc(100%-32px)] max-w-lg overflow-auto rounded-[24px] border border-white p-0 text-as-text shadow-as-lg backdrop:bg-slate-900/20 backdrop:backdrop-blur-sm",
        className,
      )}
    >
      {open && children}
    </dialog>
  );
}
