/**
 * Evidence domain types. Evidence is an artifact (with version history) that proves a
 * control is operating. It carries free-form tags and links to one or more framework
 * controls from the catalog.
 */

export interface EvidenceVersion {
  id: string;
  versionNumber: number;
  fileName: string;
  contentType: string;
  kind: string;
  sizeBytes: number;
  checksumSha256: string;
  storageKey: string;
  note?: string;
  uploadedByUserId: string;
  uploadedByName: string;
  createdAt: string;
}

export interface Evidence {
  id: string;
  tenantId: string;
  title: string;
  description?: string;
  tags: string[];
  /** Linked control ids from the framework catalog, e.g. "iso_27001:A.5.15". */
  controlIds: string[];
  versions: EvidenceVersion[];
  currentVersionId: string;
  createdByUserId: string;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
}

export interface EvidenceSummary {
  id: string;
  title: string;
  description?: string;
  tags: string[];
  controlIds: string[];
  versionCount: number;
  currentVersion: {
    fileName: string;
    kind: string;
    sizeBytes: number;
    createdAt: string;
  } | null;
  createdByName: string;
  updatedAt: string;
}

export function currentVersion(evidence: Evidence): EvidenceVersion | null {
  return (
    evidence.versions.find((v) => v.id === evidence.currentVersionId) ??
    evidence.versions.at(-1) ??
    null
  );
}

export function toEvidenceSummary(evidence: Evidence): EvidenceSummary {
  const version = currentVersion(evidence);
  return {
    id: evidence.id,
    title: evidence.title,
    description: evidence.description,
    tags: evidence.tags,
    controlIds: evidence.controlIds,
    versionCount: evidence.versions.length,
    currentVersion: version
      ? {
          fileName: version.fileName,
          kind: version.kind,
          sizeBytes: version.sizeBytes,
          createdAt: version.createdAt,
        }
      : null,
    createdByName: evidence.createdByName,
    updatedAt: evidence.updatedAt,
  };
}
