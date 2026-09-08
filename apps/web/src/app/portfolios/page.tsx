import { Suspense } from "react";
import { Card } from "@/components/ui/card";
import { PortfolioAttribution } from "@/features/portfolio/portfolio-attribution";

export default function PortfoliosPage() {
  return (
    <Suspense fallback={<Card className="h-80 animate-pulse bg-as-secondary" />}>
      <PortfolioAttribution />
    </Suspense>
  );
}
