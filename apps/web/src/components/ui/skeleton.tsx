import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-as bg-as-secondary", className)}
      aria-hidden
    />
  );
}
