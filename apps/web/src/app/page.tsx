"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { HomeDashboard } from "@/features/home/home-dashboard";

export default function HomePage() {
  const strategies = useQuery({
    queryKey: ["strategies"],
    queryFn: api.listStrategies,
  });
  const backtests = useQuery({
    queryKey: ["backtests"],
    queryFn: api.listBacktests,
  });

  return (
    <HomeDashboard
      strategies={strategies.data || []}
      backtests={backtests.data || []}
      loading={strategies.isLoading || backtests.isLoading}
      error={Boolean(strategies.isError || backtests.isError)}
      onRetry={() => {
        strategies.refetch();
        backtests.refetch();
      }}
    />
  );
}
