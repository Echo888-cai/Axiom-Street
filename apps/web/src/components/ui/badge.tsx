import { cn } from "@/lib/utils";

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "blue" | "green" | "red" | "amber";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full border border-transparent px-2.5 py-1 text-[11px] font-medium",
        tone === "neutral" && "bg-as-secondary text-as-muted",
        tone === "blue" && "bg-as-primary/10 text-as-primary",
        tone === "green" && "bg-as-positive/10 text-as-positive",
        tone === "red" && "bg-as-negative/10 text-as-negative",
        tone === "amber" && "bg-as-warning/10 text-as-warning",
        className,
      )}
    >
      {children}
    </span>
  );
}
