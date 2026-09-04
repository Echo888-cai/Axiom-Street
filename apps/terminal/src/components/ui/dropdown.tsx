import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

interface DropdownItem<T> {
  value: T;
  label: string;
  hint?: string;
}

interface DropdownProps<T> {
  value: T;
  items: DropdownItem<T>[];
  onChange: (v: T) => void;
  prefix?: string;
  className?: string;
}

/** Linear-grade dropdown: quiet trigger, floating panel, checkmark on active. */
export function Dropdown<T extends string>({
  value,
  items,
  onChange,
  prefix,
  className,
}: DropdownProps<T>) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const active = items.find((i) => i.value === value);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "interactive flex h-7 cursor-pointer items-center gap-1.5 rounded-md border px-2 text-[12.5px]",
          open
            ? "border-edge-strong bg-raised text-text"
            : "border-edge bg-panel text-text-2 hover:border-edge-strong hover:text-text",
        )}
      >
        {prefix && <span className="text-text-3">{prefix}</span>}
        <span className="font-medium">{active?.label}</span>
        <ChevronDown
          className={cn("h-3 w-3 text-text-4 transition-transform duration-200", open && "rotate-180")}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.15, ease: [0.25, 1, 0.5, 1] }}
            className="absolute top-full left-0 z-40 mt-1 min-w-[200px] overflow-hidden rounded-md border border-edge-strong bg-overlay p-1 shadow-[0_16px_48px_rgba(0,0,0,0.55)]"
          >
            {items.map((item) => {
              const isActive = item.value === value;
              return (
                <button
                  key={item.value}
                  onClick={() => {
                    onChange(item.value);
                    setOpen(false);
                  }}
                  className={cn(
                    "interactive flex w-full cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-left text-[12.5px]",
                    isActive ? "text-text" : "text-text-2 hover:bg-raised hover:text-text",
                  )}
                >
                  <span className="flex-1">{item.label}</span>
                  {item.hint && <span className="mono text-[10.5px] text-text-4">{item.hint}</span>}
                  {isActive && <Check className="h-3.5 w-3.5 text-accent" />}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
