import { Suspense } from "react";
import { ResearchDesk } from "@/features/research/research-desk";
import { Card } from "@/components/ui/card";

export default function ReportsPage() {
  return (
    <Suspense fallback={<Card className="h-80 animate-pulse bg-as-secondary" />}>
      <ResearchDesk />
    </Suspense>
  );
}
