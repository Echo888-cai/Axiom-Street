import { cn } from "@/lib/utils";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "blue" | "green" | "red" | "amber";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium",
        tone === "neutral" && "bg-as-secondary text-as-muted",
        tone === "blue" && "bg-as-primary/10 text-as-primary",
        tone === "green" && "bg-as-positive/10 text-as-positive",
        tone === "red" && "bg-as-negative/10 text-as-negative",
        tone === "amber" && "bg-[rgba(247,144,9,0.12)] text-[#b54708]",
      )}
    >
      {children}
    </span>
  );
}
