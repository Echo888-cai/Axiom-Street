"use client";

import { use } from "react";
import { BacktestStudio } from "@/features/backtests/backtest-studio";

export default function BacktestDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <BacktestStudio backtestId={id} />;
}
