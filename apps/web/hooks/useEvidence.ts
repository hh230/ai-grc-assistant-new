"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addEvidenceVersion,
  createEvidence,
  deleteEvidence,
  fetchEvidence,
  fetchEvidenceItem,
  updateEvidence,
  type CreateEvidencePayload,
  type EvidenceQuery,
  type UpdateEvidencePayload,
} from "@/lib/evidence/client";
import type { Evidence, EvidenceSummary } from "@/lib/evidence/types";

const EVIDENCE_KEY = ["evidence"] as const;

export function useEvidence(query: EvidenceQuery) {
  return useQuery<EvidenceSummary[]>({
    queryKey: [...EVIDENCE_KEY, query],
    queryFn: () => fetchEvidence(query),
  });
}

export function useEvidenceItem(id: string | null) {
  return useQuery<Evidence>({
    queryKey: [...EVIDENCE_KEY, "item", id],
    queryFn: () => fetchEvidenceItem(id as string),
    enabled: Boolean(id),
  });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: EVIDENCE_KEY });
}

export function useCreateEvidence() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: CreateEvidencePayload) => createEvidence(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateEvidence() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateEvidencePayload }) =>
      updateEvidence(id, patch),
    onSuccess: invalidate,
  });
}

export function useAddEvidenceVersion() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, file, note }: { id: string; file: File; note?: string }) =>
      addEvidenceVersion(id, file, note),
    onSuccess: invalidate,
  });
}

export function useDeleteEvidence() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => deleteEvidence(id), onSuccess: invalidate });
}
