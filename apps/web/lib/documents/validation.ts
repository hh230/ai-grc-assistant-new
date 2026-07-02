/**
 * Upload validation. The client pre-validates for UX, but the server is the authority:
 * type, size, and magic-byte sniffing all run again in the upload route. We accept PDF and
 * Word (.docx/.doc) — the formats the GRC analysis pipeline can parse.
 */

export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024; // 25 MB

export interface AcceptedType {
  kind: string;
  label: string;
  extensions: string[];
  mimeTypes: string[];
}

export const ACCEPTED_TYPES: AcceptedType[] = [
  { kind: "pdf", label: "PDF", extensions: [".pdf"], mimeTypes: ["application/pdf"] },
  {
    kind: "docx",
    label: "Word (.docx)",
    extensions: [".docx"],
    mimeTypes: ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
  },
  { kind: "doc", label: "Word (.doc)", extensions: [".doc"], mimeTypes: ["application/msword"] },
];

export const ACCEPT_ATTRIBUTE = ACCEPTED_TYPES.flatMap((t) => [
  ...t.extensions,
  ...t.mimeTypes,
]).join(",");

function extensionOf(fileName: string): string {
  const dot = fileName.lastIndexOf(".");
  return dot === -1 ? "" : fileName.slice(dot).toLowerCase();
}

export function classifyByName(fileName: string, contentType: string): AcceptedType | null {
  const ext = extensionOf(fileName);
  return (
    ACCEPTED_TYPES.find((t) => t.extensions.includes(ext) || t.mimeTypes.includes(contentType)) ??
    null
  );
}

export interface ValidationFailure {
  ok: false;
  reason: string;
}
export interface ValidationSuccess {
  ok: true;
  kind: string;
  contentType: string;
}
export type ValidationResult = ValidationFailure | ValidationSuccess;

/** Fast client-side check (no bytes): extension/MIME + size. */
export function validateFileMeta(
  fileName: string,
  contentType: string,
  size: number,
): ValidationResult {
  if (size <= 0) return { ok: false, reason: "File is empty." };
  if (size > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      reason: `File exceeds the ${Math.round(MAX_UPLOAD_BYTES / (1024 * 1024))} MB limit.`,
    };
  }
  const type = classifyByName(fileName, contentType);
  if (!type) return { ok: false, reason: "Unsupported file type. Upload a PDF or Word document." };
  return { ok: true, kind: type.kind, contentType: type.mimeTypes[0] ?? contentType };
}

/** Magic-byte sniff — content must actually be what its name/MIME claims. */
function sniffKind(bytes: Buffer): "pdf" | "zip" | "ole" | "unknown" {
  if (bytes.length >= 4 && bytes.toString("latin1", 0, 4) === "%PDF") return "pdf";
  // DOCX is a ZIP container (PK\x03\x04); legacy DOC is an OLE compound file (D0 CF 11 E0).
  if (
    bytes.length >= 4 &&
    bytes[0] === 0x50 &&
    bytes[1] === 0x4b &&
    bytes[2] === 0x03 &&
    bytes[3] === 0x04
  ) {
    return "zip";
  }
  if (
    bytes.length >= 8 &&
    bytes[0] === 0xd0 &&
    bytes[1] === 0xcf &&
    bytes[2] === 0x11 &&
    bytes[3] === 0xe0
  ) {
    return "ole";
  }
  return "unknown";
}

/** Authoritative server-side validation: metadata + true file signature. */
export function validateUpload(
  fileName: string,
  contentType: string,
  bytes: Buffer,
): ValidationResult {
  const meta = validateFileMeta(fileName, contentType, bytes.length);
  if (!meta.ok) return meta;

  const signature = sniffKind(bytes);
  const expected: Record<string, ReturnType<typeof sniffKind>[]> = {
    pdf: ["pdf"],
    docx: ["zip"],
    doc: ["ole"],
  };
  if (!expected[meta.kind]?.includes(signature)) {
    return { ok: false, reason: "File contents do not match a valid PDF or Word document." };
  }
  return meta;
}
