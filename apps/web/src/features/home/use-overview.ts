"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useOverview() {
  return useQuery({
    queryKey: ["overview"],
    queryFn: api.getOverview,
    // Worker completions can happen while another page or client is open.
    refetchInterval: 5_000,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
}
