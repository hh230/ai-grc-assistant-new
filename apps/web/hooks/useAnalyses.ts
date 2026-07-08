"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteAnalysis,
  fetchAnalyses,
  fetchAnalysisUsage,
  fetchAnalysisVersions,
  renameAnalysis,
  startAnalysis,
} from "@/lib/analysis/client";
import type { AnalysisRecord, AnalysisUsage } from "@/lib/analysis/types";

const ANALYSES_KEY = ["analyses"] as const;
const USAGE_KEY = [...ANALYSES_KEY, "usage"] as const;
const versionsKey = (documentId: string) => [...ANALYSES_KEY, "versions", documentId] as const;

/** Poll while any analysis is still in flight. */
function pollWhileActive(records: AnalysisRecord[] | undefined): number | false {
  return records?.some((r) => r.status === "processing" || r.status === "queued") ? 2000 : false;
}

/** Latest version per document — the analysis history list. */
export function useAnalyses() {
  return useQuery({
    queryKey: ANALYSES_KEY,
    queryFn: fetchAnalyses,
    refetchInterval: (query) => pollWhileActive(query.state.data),
  });
}

/** The current user's remaining beta analysis budget for today. */
export function useAnalysisUsage() {
  return useQuery<AnalysisUsage>({
    queryKey: USAGE_KEY,
    queryFn: fetchAnalysisUsage,
  });
}

/** Every version for a document, newest first. `data[0]` is the latest, if any exist. */
export function useAnalysisVersions(documentId: string) {
  return useQuery<AnalysisRecord[]>({
    queryKey: versionsKey(documentId),
    queryFn: () => fetchAnalysisVersions(documentId),
    refetchInterval: (query) => pollWhileActive(query.state.data),
  });
}

export function useStartAnalysis(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => startAnalysis(documentId),
    onSettled: () => {
      // Refresh the remaining-budget counter whether the run started or was rejected — a
      // 429 still means the count is at its cap, and a successful run consumed one.
      void queryClient.invalidateQueries({ queryKey: USAGE_KEY });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: versionsKey(documentId) });
      void queryClient.invalidateQueries({ queryKey: ANALYSES_KEY });
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useRenameAnalysis(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ analysisId, title }: { analysisId: string; title: string }) =>
      renameAnalysis(analysisId, title),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: versionsKey(documentId) });
      void queryClient.invalidateQueries({ queryKey: ANALYSES_KEY });
    },
  });
}

export function useDeleteAnalysis(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (analysisId: string) => deleteAnalysis(analysisId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: versionsKey(documentId) });
      void queryClient.invalidateQueries({ queryKey: ANALYSES_KEY });
    },
  });
}
