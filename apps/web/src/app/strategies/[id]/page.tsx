"use client";

import { use } from "react";
import { StrategyLab } from "@/features/strategy-lab/strategy-lab";

export default function StrategyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <StrategyLab strategyId={id} />;
}
