import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          "h-9 rounded-lg border border-aq-border bg-aq-bg px-3 text-sm text-aq-text outline-none transition-colors duration-aq",
          "placeholder:text-aq-muted",
          "focus:border-aq-primary/40 focus:ring-2 focus-visible:ring-aq-primary/20",
          className,
        )}
        {...props}
      />
    );
  },
);
