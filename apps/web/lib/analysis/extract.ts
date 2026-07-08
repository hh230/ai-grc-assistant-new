/**
 * Text extraction from uploaded documents. PDF via unpdf (a pdf.js build compiled for
 * serverless — pure text extraction, no canvas/DOMMatrix dependency, unlike pdf-parse's
 * default Node build), DOCX via mammoth. Behind a single `extractText` dispatch so the
 * pipeline is format-agnostic. Node-only.
 */

import mammoth from "mammoth";
import { extractText as extractPdfText, getDocumentProxy } from "unpdf";

export interface ExtractedText {
  text: string;
  pageCount?: number;
}

export async function extractText(kind: string, bytes: Buffer): Promise<ExtractedText> {
  switch (kind) {
    case "pdf":
      return extractPdf(bytes);
    case "docx":
      return extractDocx(bytes);
    case "doc":
      throw new Error(
        "Legacy .doc files are not supported for analysis. Please upload a .docx or PDF.",
      );
    default:
      throw new Error(`Unsupported document type for analysis: ${kind}`);
  }
}

async function extractPdf(bytes: Buffer): Promise<ExtractedText> {
  const pdf = await getDocumentProxy(new Uint8Array(bytes));
  const { totalPages, text } = await extractPdfText(pdf, { mergePages: true });
  return { text: normalize(text), pageCount: totalPages };
}

async function extractDocx(bytes: Buffer): Promise<ExtractedText> {
  const { value } = await mammoth.extractRawText({ buffer: bytes });
  return { text: normalize(value) };
}

/** Collapse noisy whitespace while preserving paragraph boundaries. */
function normalize(text: string): string {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
