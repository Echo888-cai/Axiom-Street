"use client";

import { use } from "react";
import { UniverseDetail } from "@/features/universes/universe-detail";

export default function UniverseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <UniverseDetail universeId={id} />;
}
