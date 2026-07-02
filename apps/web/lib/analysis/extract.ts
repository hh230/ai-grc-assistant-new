/**
 * Text extraction from uploaded documents. PDF via pdf-parse (pdfjs under the hood), DOCX
 * via mammoth. Behind a single `extractText` dispatch so the pipeline is format-agnostic.
 * Node-only.
 */

import mammoth from "mammoth";
import { PDFParse } from "pdf-parse";

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
  const parser = new PDFParse({ data: new Uint8Array(bytes) });
  try {
    const result = await parser.getText();
    return { text: normalize(result.text), pageCount: result.pages?.length };
  } finally {
    await parser.destroy();
  }
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
