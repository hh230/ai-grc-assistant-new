"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchReport } from "@/lib/reports/client";
import type { Report, ReportKind } from "@/lib/reports/types";

export function useReport(kind: ReportKind) {
  return useQuery<Report>({
    queryKey: ["report", kind],
    queryFn: () => fetchReport(kind),
  });
}
