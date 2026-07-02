/** Browser-side evidence API client. */

import type { Evidence, EvidenceSummary } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export interface EvidenceQuery {
  search?: string;
  tag?: string;
  controlId?: string;
}

export async function fetchEvidence(query: EvidenceQuery = {}): Promise<EvidenceSummary[]> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.tag) params.set("tag", query.tag);
  if (query.controlId) params.set("controlId", query.controlId);
  const response = await fetch(`/api/evidence?${params.toString()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { evidence: EvidenceSummary[] }).evidence;
}

export async function fetchEvidenceItem(id: string): Promise<Evidence> {
  const response = await fetch(`/api/evidence/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { evidence: Evidence }).evidence;
}

export interface CreateEvidencePayload {
  title: string;
  description?: string;
  tags: string[];
  controlIds: string[];
  file: File;
}

export async function createEvidence(payload: CreateEvidencePayload): Promise<Evidence> {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("title", payload.title);
  if (payload.description) form.append("description", payload.description);
  form.append("tags", JSON.stringify(payload.tags));
  form.append("controlIds", JSON.stringify(payload.controlIds));
  const response = await fetch("/api/evidence", { method: "POST", body: form });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { evidence: Evidence }).evidence;
}

export interface UpdateEvidencePayload {
  title?: string;
  description?: string;
  tags?: string[];
  controlIds?: string[];
}

export async function updateEvidence(id: string, patch: UpdateEvidencePayload): Promise<Evidence> {
  const response = await fetch(`/api/evidence/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { evidence: Evidence }).evidence;
}

export async function addEvidenceVersion(id: string, file: File, note?: string): Promise<Evidence> {
  const form = new FormData();
  form.append("file", file);
  if (note) form.append("note", note);
  const response = await fetch(`/api/evidence/${id}/versions`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { evidence: Evidence }).evidence;
}

export async function deleteEvidence(id: string): Promise<void> {
  const response = await fetch(`/api/evidence/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await parseError(response));
}
