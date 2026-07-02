"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteConversation, fetchConversations } from "@/lib/chat/client";
import type { ConversationSummary } from "@/lib/chat/types";

const CONVERSATIONS_KEY = ["conversations"] as const;

export function useConversations() {
  return useQuery<ConversationSummary[]>({
    queryKey: CONVERSATIONS_KEY,
    queryFn: fetchConversations,
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY }),
  });
}

export function useRefreshConversations() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
}
