import { cn } from "@/lib/utils";

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: Props) {
  return (
    <button
      className={cn(
        "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-medium outline-none transition-all duration-aq",
        "focus-visible:ring-2 focus-visible:ring-aq-primary/30 focus-visible:ring-offset-2",
        "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
        size === "sm" ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm",
        variant === "primary" && "bg-aq-primary text-white shadow-sm hover:bg-[#0f6aef]",
        variant === "secondary" &&
          "border border-aq-border bg-aq-bg text-aq-text hover:border-aq-primary/25 hover:bg-aq-secondary",
        variant === "ghost" && "text-aq-muted hover:bg-aq-secondary hover:text-aq-text",
        variant === "danger" && "bg-aq-negative text-white hover:opacity-90",
        className,
      )}
      {...props}
    />
  );
}
