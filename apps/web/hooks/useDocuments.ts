"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, fetchDocuments } from "@/lib/documents/client";
import type { DocumentDto } from "@/lib/documents/types";

const DOCUMENTS_KEY = ["documents"] as const;

export function useDocuments() {
  return useQuery<DocumentDto[]>({
    queryKey: DOCUMENTS_KEY,
    queryFn: fetchDocuments,
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY }),
  });
}

/** Call after one or more uploads complete to refresh the document list. */
export function useRefreshDocuments() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY });
}
