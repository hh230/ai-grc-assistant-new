/**
 * Document domain types. An uploaded document is the platform's "knowledge source" — the
 * raw artifact that the P4 analysis pipeline parses, chunks, embeds, and grounds answers
 * on. Status tracks its journey from upload through AI processing.
 */

export const DOCUMENT_STATUSES = [
  "uploaded", // stored, awaiting processing
  "queued", // accepted by the analysis pipeline
  "processing", // parsing / chunking / embedding in progress
  "processed", // indexed and ready for retrieval
  "failed", // processing failed (see statusDetail)
] as const;
export type DocumentStatus = (typeof DOCUMENT_STATUSES)[number];

/**
 * Mandatory classification chosen in the upload wizard (V2-P2.5). Passed into the assess
 * prompt as context and used to filter the analysis history view.
 */
export const DOCUMENT_CATEGORIES = [
  "governance",
  "risk_register",
  "policies",
  "contracts",
  "compliance",
  "internal_audit",
  "cybersecurity",
  "other",
] as const;
export type DocumentCategory = (typeof DOCUMENT_CATEGORIES)[number];

export const DOCUMENT_CATEGORY_LABELS: Record<DocumentCategory, string> = {
  governance: "Governance",
  risk_register: "Risk Register",
  policies: "Policies",
  contracts: "Contracts",
  compliance: "Compliance",
  internal_audit: "Internal Audit",
  cybersecurity: "Cybersecurity",
  other: "Other",
};

export interface DocumentRecord {
  id: string;
  tenantId: string;
  uploadedByUserId: string;
  uploadedByName: string;
  fileName: string;
  contentType: string;
  /** Canonical short kind for UI/icons: "pdf" | "docx" | "doc". */
  kind: string;
  category: DocumentCategory;
  sizeBytes: number;
  checksumSha256: string;
  storageKey: string;
  status: DocumentStatus;
  statusDetail?: string;
  createdAt: string;
  updatedAt: string;
}

/** The shape returned to clients (currently identical — no server-only fields to strip). */
export type DocumentDto = DocumentRecord;

export function toDocumentDto(record: DocumentRecord): DocumentDto {
  return record;
}
