"use client";

import { EmptyState } from "@/components/ui/empty-state";
import { useT } from "@/lib/i18n";

export function ScopeEmpty({ variant }: { variant: "no-scope" | "not-found" }) {
  const t = useT();
  return (
    <div className="flex flex-1 flex-col justify-center">
      <EmptyState
        title={
          variant === "no-scope"
            ? t("copilot.empty.title")
            : t("copilot.notFound.title")
        }
        description={
          variant === "no-scope"
            ? t("copilot.empty.description")
            : t("copilot.notFound.description")
        }
      />
    </div>
  );
}
