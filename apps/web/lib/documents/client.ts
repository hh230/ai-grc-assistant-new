/**
 * Browser-side document API client. `uploadDocument` uses XMLHttpRequest because `fetch`
 * cannot report upload progress; everything else uses `fetch`.
 */

import type { DocumentCategory, DocumentDto } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function fetchDocuments(): Promise<DocumentDto[]> {
  const response = await fetch("/api/documents", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  const data = (await response.json()) as { documents: DocumentDto[] };
  return data.documents;
}

export async function deleteDocument(id: string): Promise<void> {
  const response = await fetch(`/api/documents/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await parseError(response));
}

export interface UploadHandlers {
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

export interface UploadResponse {
  document: DocumentDto;
  /** true when this exact file content was already uploaded — no new document was created. */
  duplicate: boolean;
}

export function uploadDocument(
  file: File,
  category: DocumentCategory,
  handlers: UploadHandlers = {},
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    form.append("category", category);

    xhr.open("POST", "/api/documents");
    xhr.responseType = "json";

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && handlers.onProgress) {
        handlers.onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      const body = xhr.response as UploadResponse & { error?: string };
      if (xhr.status >= 200 && xhr.status < 300 && body?.document) {
        resolve(body);
      } else {
        reject(new Error(body?.error ?? `Upload failed (${xhr.status}).`));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload."));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));

    handlers.signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(form);
  });
}
