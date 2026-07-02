/**
 * Evidence upload validation. Broader than document analysis inputs — evidence is commonly a
 * PDF, Word file, or a screenshot — but still authoritative server-side: size + type + magic
 * bytes. Node-only.
 */

export const MAX_EVIDENCE_BYTES = 25 * 1024 * 1024; // 25 MB

interface EvidenceType {
  kind: string;
  extensions: string[];
  mimeTypes: string[];
  /** Magic-byte predicate over the leading bytes. */
  sniff: (bytes: Buffer) => boolean;
}

const startsWith = (bytes: Buffer, sig: number[]): boolean =>
  bytes.length >= sig.length && sig.every((b, i) => bytes[i] === b);

const TYPES: EvidenceType[] = [
  {
    kind: "pdf",
    extensions: [".pdf"],
    mimeTypes: ["application/pdf"],
    sniff: (b) => b.length >= 4 && b.toString("latin1", 0, 4) === "%PDF",
  },
  {
    kind: "docx",
    extensions: [".docx"],
    mimeTypes: ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    sniff: (b) => startsWith(b, [0x50, 0x4b, 0x03, 0x04]),
  },
  {
    kind: "doc",
    extensions: [".doc"],
    mimeTypes: ["application/msword"],
    sniff: (b) => startsWith(b, [0xd0, 0xcf, 0x11, 0xe0]),
  },
  {
    kind: "png",
    extensions: [".png"],
    mimeTypes: ["image/png"],
    sniff: (b) => startsWith(b, [0x89, 0x50, 0x4e, 0x47]),
  },
  {
    kind: "jpg",
    extensions: [".jpg", ".jpeg"],
    mimeTypes: ["image/jpeg"],
    sniff: (b) => startsWith(b, [0xff, 0xd8, 0xff]),
  },
];

export const EVIDENCE_ACCEPT = TYPES.flatMap((t) => [...t.extensions, ...t.mimeTypes]).join(",");

function extensionOf(fileName: string): string {
  const dot = fileName.lastIndexOf(".");
  return dot === -1 ? "" : fileName.slice(dot).toLowerCase();
}

export interface EvidenceValidationResult {
  ok: boolean;
  reason?: string;
  kind?: string;
  contentType?: string;
}

export function validateEvidenceUpload(
  fileName: string,
  contentType: string,
  bytes: Buffer,
): EvidenceValidationResult {
  if (bytes.length === 0) return { ok: false, reason: "File is empty." };
  if (bytes.length > MAX_EVIDENCE_BYTES) {
    return {
      ok: false,
      reason: `File exceeds the ${Math.round(MAX_EVIDENCE_BYTES / (1024 * 1024))} MB limit.`,
    };
  }
  const ext = extensionOf(fileName);
  const type = TYPES.find((t) => t.extensions.includes(ext) || t.mimeTypes.includes(contentType));
  if (!type) {
    return {
      ok: false,
      reason: "Unsupported file type. Upload a PDF, Word document, or image (PNG/JPG).",
    };
  }
  if (!type.sniff(bytes)) {
    return { ok: false, reason: "File contents do not match the expected format." };
  }
  return { ok: true, kind: type.kind, contentType: type.mimeTypes[0] ?? contentType };
}
