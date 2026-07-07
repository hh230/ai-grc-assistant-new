"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveAccessRequest,
  fetchAccessRequests,
  rejectAccessRequest,
  type ApproveAccessRequestResponse,
} from "@/lib/accessRequests/client";
import type { AccessRequest } from "@/lib/accessRequests/types";
import type { InvitedRole } from "@/lib/invitations/types";

const QUERY_KEY_ROOT = "access-requests";

export function usePendingAccessRequests() {
  return useQuery<AccessRequest[]>({
    queryKey: [QUERY_KEY_ROOT, "pending"],
    queryFn: () => fetchAccessRequests(),
    select: (requests) => requests.filter((request) => request.status === "pending"),
  });
}

function useInvalidateAccessRequestQueries() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: [QUERY_KEY_ROOT] });
}

export function useApproveAccessRequest() {
  const invalidate = useInvalidateAccessRequestQueries();
  return useMutation<ApproveAccessRequestResponse, Error, { id: string; invitedRole: InvitedRole }>({
    mutationFn: ({ id, invitedRole }) => approveAccessRequest(id, invitedRole),
    onSuccess: () => invalidate(),
  });
}

export function useRejectAccessRequest() {
  const invalidate = useInvalidateAccessRequestQueries();
  return useMutation<AccessRequest, Error, string>({
    mutationFn: (id: string) => rejectAccessRequest(id),
    onSuccess: () => invalidate(),
  });
}
