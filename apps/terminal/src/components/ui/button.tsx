import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "ghost" | "outline" | "quiet";
type Size = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  primary:
    "bg-accent text-[#14100a] font-medium hover:bg-accent-hi shadow-[inset_0_1px_0_rgba(255,255,255,0.25)]",
  ghost: "text-text-2 hover:text-text hover:bg-raised",
  outline:
    "border border-edge-strong text-text-2 hover:text-text hover:border-text-3 hover:bg-raised/60",
  quiet: "text-text-3 hover:text-text-2",
};

const sizes: Record<Size, string> = {
  sm: "h-6.5 px-2 text-xs gap-1.5",
  md: "h-7.5 px-3 text-[13px] gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "ghost", size = "md", className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "interactive pressable inline-flex cursor-pointer items-center justify-center rounded-md font-sans whitespace-nowrap select-none disabled:pointer-events-none disabled:opacity-40",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";

export const IconButton = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "ghost", size = "sm", className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "interactive pressable inline-flex cursor-pointer items-center justify-center rounded-md text-text-3 hover:bg-raised hover:text-text-2 disabled:pointer-events-none disabled:opacity-40",
        size === "sm" ? "h-6.5 w-6.5" : "h-7.5 w-7.5",
        variant === "outline" && "border border-edge-strong",
        className,
      )}
      {...props}
    />
  ),
);
IconButton.displayName = "IconButton";
