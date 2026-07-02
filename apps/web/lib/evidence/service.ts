/**
 * Evidence application service. Manages evidence artifacts with version history, tags, and
 * control linkage. Enforces RBAC on the `evidence` resource and keeps everything tenant-
 * scoped. Reuses the P3 blob store for the underlying files. Node-only.
 */

import { randomUUID } from "node:crypto";
import { ForbiddenError, NotFoundError, ValidationError } from "@/lib/errors";
import { can } from "@/lib/auth/permissions";
import type { ActorContext } from "@/lib/auth/actor";
import { blobStore, sha256 } from "@/lib/storage/blob-store";
import { isKnownControl } from "@/lib/frameworks/catalog";
import { evidenceRepository } from "./repository";
import { validateEvidenceUpload } from "./validation";
import { currentVersion, type Evidence, type EvidenceVersion } from "./types";

export interface EvidenceFileInput {
  fileName: string;
  contentType: string;
  bytes: Buffer;
  note?: string;
}

export interface CreateEvidenceInput {
  title: string;
  description?: string;
  tags?: string[];
  controlIds?: string[];
  file: EvidenceFileInput;
}

export interface EvidenceFilter {
  search?: string;
  tag?: string;
  controlId?: string;
}

function ensure(actor: ActorContext, action: "create" | "read" | "update" | "delete"): void {
  if (!can(actor.roles, action, "evidence")) {
    throw new ForbiddenError(`You are not permitted to ${action} evidence.`);
  }
}

function cleanTags(tags?: string[]): string[] {
  return Array.from(new Set((tags ?? []).map((t) => t.trim().toLowerCase()).filter(Boolean))).slice(
    0,
    20,
  );
}

function cleanControlIds(controlIds?: string[]): string[] {
  return Array.from(new Set((controlIds ?? []).filter((id) => isKnownControl(id)))).slice(0, 50);
}

async function storeVersion(
  actor: ActorContext,
  evidenceId: string,
  versionNumber: number,
  file: EvidenceFileInput,
): Promise<EvidenceVersion> {
  const validation = validateEvidenceUpload(file.fileName, file.contentType, file.bytes);
  if (!validation.ok) throw new ValidationError(validation.reason ?? "Invalid file.");

  const versionId = randomUUID();
  const storageKey = `${actor.tenantId}/evidence/${evidenceId}/${versionId}`;
  await blobStore.put(storageKey, file.bytes);

  return {
    id: versionId,
    versionNumber,
    fileName: file.fileName.split(/[/\\]/).pop() ?? file.fileName,
    contentType: validation.contentType ?? file.contentType,
    kind: validation.kind ?? "file",
    sizeBytes: file.bytes.length,
    checksumSha256: sha256(file.bytes),
    storageKey,
    note: file.note,
    uploadedByUserId: actor.userId,
    uploadedByName: actor.userName,
    createdAt: new Date().toISOString(),
  };
}

export async function listEvidence(
  actor: ActorContext,
  filter: EvidenceFilter = {},
): Promise<Evidence[]> {
  ensure(actor, "read");
  let items = await evidenceRepository.list(actor.tenantId);
  const search = filter.search?.trim().toLowerCase();
  if (search) {
    items = items.filter(
      (e) =>
        e.title.toLowerCase().includes(search) ||
        (e.description ?? "").toLowerCase().includes(search) ||
        e.tags.some((t) => t.includes(search)),
    );
  }
  if (filter.tag) items = items.filter((e) => e.tags.includes(filter.tag!.toLowerCase()));
  if (filter.controlId) items = items.filter((e) => e.controlIds.includes(filter.controlId!));
  return items;
}

export async function getEvidence(actor: ActorContext, id: string): Promise<Evidence> {
  ensure(actor, "read");
  const evidence = await evidenceRepository.get(actor.tenantId, id);
  if (!evidence) throw new NotFoundError("Evidence not found.");
  return evidence;
}

export async function createEvidence(
  actor: ActorContext,
  input: CreateEvidenceInput,
): Promise<Evidence> {
  ensure(actor, "create");
  const title = input.title.trim();
  if (!title) throw new ValidationError("A title is required.");

  const id = randomUUID();
  const version = await storeVersion(actor, id, 1, input.file);
  const now = new Date().toISOString();
  const evidence: Evidence = {
    id,
    tenantId: actor.tenantId,
    title,
    description: input.description?.trim() || undefined,
    tags: cleanTags(input.tags),
    controlIds: cleanControlIds(input.controlIds),
    versions: [version],
    currentVersionId: version.id,
    createdByUserId: actor.userId,
    createdByName: actor.userName,
    createdAt: now,
    updatedAt: now,
  };
  return evidenceRepository.create(evidence);
}

export interface UpdateEvidenceInput {
  title?: string;
  description?: string;
  tags?: string[];
  controlIds?: string[];
}

export async function updateEvidence(
  actor: ActorContext,
  id: string,
  input: UpdateEvidenceInput,
): Promise<Evidence> {
  ensure(actor, "update");
  const updated = await evidenceRepository.update(actor.tenantId, id, (evidence) => ({
    ...evidence,
    title: input.title?.trim() || evidence.title,
    description:
      input.description === undefined
        ? evidence.description
        : input.description.trim() || undefined,
    tags: input.tags === undefined ? evidence.tags : cleanTags(input.tags),
    controlIds:
      input.controlIds === undefined ? evidence.controlIds : cleanControlIds(input.controlIds),
    updatedAt: new Date().toISOString(),
  }));
  if (!updated) throw new NotFoundError("Evidence not found.");
  return updated;
}

export async function addEvidenceVersion(
  actor: ActorContext,
  id: string,
  file: EvidenceFileInput,
): Promise<Evidence> {
  ensure(actor, "update");
  const existing = await evidenceRepository.get(actor.tenantId, id);
  if (!existing) throw new NotFoundError("Evidence not found.");

  const version = await storeVersion(actor, id, existing.versions.length + 1, file);
  const updated = await evidenceRepository.update(actor.tenantId, id, (evidence) => ({
    ...evidence,
    versions: [...evidence.versions, version],
    currentVersionId: version.id,
    updatedAt: new Date().toISOString(),
  }));
  if (!updated) throw new NotFoundError("Evidence not found.");
  return updated;
}

export async function deleteEvidence(actor: ActorContext, id: string): Promise<void> {
  ensure(actor, "delete");
  const removed = await evidenceRepository.delete(actor.tenantId, id);
  if (!removed) throw new NotFoundError("Evidence not found.");
  // Best-effort cleanup of all version blobs.
  await Promise.all(
    removed.versions.map((v) => blobStore.delete(v.storageKey).catch(() => undefined)),
  );
}

export async function readEvidenceVersion(
  actor: ActorContext,
  id: string,
  versionId: string,
): Promise<{ version: EvidenceVersion; bytes: Buffer }> {
  const evidence = await getEvidence(actor, id);
  const version =
    evidence.versions.find((v) => v.id === versionId) ??
    (versionId === "current" ? currentVersion(evidence) : null);
  if (!version) throw new NotFoundError("Evidence version not found.");
  const bytes = await blobStore.get(version.storageKey);
  return { version, bytes };
}
