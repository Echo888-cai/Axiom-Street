import { cn } from "@/lib/cn";

interface TabsProps {
  items: string[];
  value: string;
  onChange: (v: string) => void;
  className?: string;
}

/** Underline tabs — terminal convention, not pill spam. */
export function Tabs({ items, value, onChange, className }: TabsProps) {
  return (
    <div className={cn("flex items-center gap-0.5 border-b border-edge", className)}>
      {items.map((item) => {
        const active = item === value;
        return (
          <button
            key={item}
            onClick={() => onChange(item)}
            className={cn(
              "interactive relative -mb-px cursor-pointer px-3 pt-1.5 pb-2 text-[13px] select-none",
              active ? "text-text" : "text-text-3 hover:text-text-2",
            )}
          >
            {item}
            <span
              className={cn(
                "absolute inset-x-2.5 bottom-0 h-px transition-colors duration-200",
                active ? "bg-accent" : "bg-transparent",
              )}
            />
          </button>
        );
      })}
    </div>
  );
}

/** Compact segmented control — timeframes, chart modes. */
export function Segmented<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: readonly T[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-px rounded-md border border-edge bg-sunken p-0.5",
        className,
      )}
    >
      {items.map((item) => {
        const active = item === value;
        return (
          <button
            key={item}
            onClick={() => onChange(item)}
            className={cn(
              "interactive pressable mono h-5.5 cursor-pointer rounded px-2 text-[11px] select-none",
              active
                ? "bg-raised text-text shadow-[0_1px_2px_rgba(0,0,0,0.4)]"
                : "text-text-3 hover:text-text-2",
            )}
          >
            {item}
          </button>
        );
      })}
    </div>
  );
}
