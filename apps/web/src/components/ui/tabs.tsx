import { cn } from "@/lib/utils";

export function Tabs({
  value,
  onChange,
  items,
}: {
  value: string;
  onChange: (id: string) => void;
  items: { id: string; label: string }[];
}) {
  return (
    <div className="inline-flex max-w-full flex-wrap gap-0.5 rounded-xl border border-as-border bg-as-secondary/70 p-1">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          aria-pressed={value === item.id}
          className={cn(
            "cursor-pointer min-h-10 rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-as",
            value === item.id
              ? "bg-as-bg text-as-text shadow-[0_1px_4px_rgba(20,30,45,0.10)]"
              : "text-as-muted hover:text-as-text",
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
