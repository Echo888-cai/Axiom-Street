"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { HomeDashboard } from "@/features/home/home-dashboard";

import { useOverview } from "@/features/home/use-overview";

export default function HomePage() {
  const overview = useOverview();
  const strategies = useQuery({
    queryKey: ["strategies"],
    queryFn: api.listStrategies,
  });
  const backtests = useQuery({
    queryKey: ["backtests"],
    queryFn: () => api.listBacktests(),
  });

  return (
    <HomeDashboard
      overview={overview.data}
      summaryLoading={overview.isLoading}
      summaryError={overview.isError}
      strategies={strategies.data || []}
      backtests={backtests.data || []}
      loading={strategies.isLoading || backtests.isLoading}
      error={Boolean(strategies.isError || backtests.isError)}
      onRetry={() => {
        overview.refetch();
        strategies.refetch();
        backtests.refetch();
      }}
    />
  );
}
