"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchMyOrganizations } from "@/lib/organizations/client";

const ORGANIZATIONS_KEY = ["organizations"] as const;

export function useOrganizations() {
  return useQuery({
    queryKey: ORGANIZATIONS_KEY,
    queryFn: fetchMyOrganizations,
  });
}
