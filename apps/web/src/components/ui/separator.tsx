"use client";

import { cn } from "@/lib/utils";

export function Separator({
  className,
  orientation = "horizontal",
  ...props
}: React.HTMLAttributes<HTMLHRElement> & {
  orientation?: "horizontal" | "vertical";
}) {
  return (
    <hr
      className={cn(
        "bg-as-border",
        orientation === "horizontal" ? "w-full h-px" : "h-full w-px",
        className,
      )}
      {...props}
    />
  );
}
