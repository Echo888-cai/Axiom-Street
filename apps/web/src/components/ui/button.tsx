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
        "inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl [&>.lucide]:shrink-0 whitespace-nowrap select-none font-medium outline-none transition-all duration-as",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-as-primary/60 focus-visible:ring-offset-2",
        "enabled:active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none",
        size === "sm"
          ? "min-h-11 px-3.5 py-2 text-xs"
          : "min-h-11 px-5 py-2.5 text-[13px]",
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
