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
        "inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl whitespace-nowrap font-medium outline-none transition-all duration-as",
        "focus-visible:ring-2 focus-visible:ring-as-primary/30 focus-visible:ring-offset-2",
        "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
        size === "sm"
          ? "min-h-9 px-3.5 py-2 text-xs"
          : "min-h-11 px-4 py-2.5 text-[13px]",
        variant === "primary" &&
          "as-button-primary border border-transparent text-white",
        variant === "secondary" &&
          "as-button-secondary border border-as-border text-as-text",
        variant === "ghost" &&
          "text-as-muted hover:bg-as-secondary hover:text-as-text",
        variant === "danger" && "bg-as-negative text-white hover:opacity-90",
        className,
      )}
      {...props}
    />
  );
}
