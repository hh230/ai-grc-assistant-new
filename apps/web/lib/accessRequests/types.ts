/** A visitor's request to gain access to the platform (KI-P9, ADR-0034, PUBLIC FLOW). */

export type AccessRequestStatus = "pending" | "approved" | "rejected";

export interface AccessRequest {
  id: string;
  name: string;
  email: string;
  organizationName: string;
  roleTitle: string;
  message: string | null;
  status: AccessRequestStatus;
  createdAt: string;
  reviewedAt: string | null;
  reviewedBy: string | null;
}
