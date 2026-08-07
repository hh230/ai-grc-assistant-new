/** Browser-side Knowledge Console client — calls this app's own `/api/knowledge/*` routes
 * (ADR 0067). Mirrors `lib/planExecution/client.ts`'s shape. */

import type { KnowledgeOutcome, ReleaseAction } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

async function send<T>(path: string, method: "POST" | "PUT", body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as T;
}

export function actOnRelease(releaseId: string, action: ReleaseAction): Promise<KnowledgeOutcome> {
  return send<KnowledgeOutcome>(`/api/knowledge/releases/${releaseId}/${action}`, "POST");
}

export function generateRelease(industrySlug: string): Promise<KnowledgeOutcome> {
  return send<KnowledgeOutcome>("/api/knowledge/releases", "POST", {
    industrySlug,
  });
}

/** Activation and rollback are the same call: which release the industry serves. */
export function setActiveRelease(
  industrySlug: string,
  releaseId: string,
  reason: string,
): Promise<KnowledgeOutcome> {
  return send<KnowledgeOutcome>(
    `/api/knowledge/industries/${industrySlug}/active-release`,
    "PUT",
    { releaseId, reason },
  );
}

export function importAuthoredPack(industrySlug: string): Promise<KnowledgeOutcome> {
  return send<KnowledgeOutcome>(`/api/knowledge/packs/${industrySlug}/import`, "POST");
}

export function registerIndustry(slug: string, canonicalNameAr: string): Promise<{ ok: true }> {
  return send<{ ok: true }>("/api/knowledge/industries", "POST", { slug, canonicalNameAr });
}
