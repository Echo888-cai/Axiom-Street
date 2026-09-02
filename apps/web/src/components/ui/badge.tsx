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
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium",
        tone === "neutral" && "bg-as-secondary text-as-muted",
        tone === "blue" && "bg-[rgba(22,119,255,0.1)] text-as-primary",
        tone === "green" && "bg-[rgba(18,183,106,0.1)] text-as-positive",
        tone === "red" && "bg-[rgba(240,68,56,0.1)] text-as-negative",
        tone === "amber" && "bg-[rgba(247,144,9,0.12)] text-[#b54708]",
      )}
    >
      {children}
    </span>
  );
}
