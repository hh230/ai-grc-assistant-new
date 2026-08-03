"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchMissions } from "@/lib/missions/client";
import type { Mission } from "@/lib/missions/types";

const MISSIONS_KEY = ["missions"] as const;

export function useMissions() {
  return useQuery<Mission[]>({
    queryKey: MISSIONS_KEY,
    queryFn: fetchMissions,
  });
}
