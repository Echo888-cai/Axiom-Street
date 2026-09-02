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
    <div className="inline-flex rounded-xl bg-as-secondary p-1">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          aria-pressed={value === item.id}
          className={cn(
            "cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-as",
            value === item.id
              ? "bg-as-bg text-as-text shadow-sm"
              : "text-as-muted hover:text-as-text",
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
