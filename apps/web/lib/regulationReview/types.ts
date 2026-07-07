/** Domain types for the Regulation Review queue (Knowledge Intelligence KI-P7, ADR-0031) —
 * camelCase mirrors of apps/api's `/regulation-review/*` response shapes. */

export interface RegulationSourceSummary {
  id: string;
  shortCode: string;
  titleAr: string;
  titleEn: string | null;
  authority: string;
  jurisdiction: string;
  knowledgeDomain: string;
  documentType: string;
  boeSourceUrl: string;
}

export interface PendingRegulationVersion {
  versionId: string;
  versionLabel: string;
  status: string;
  officialCitation: string | null;
  contentHash: string;
  createdAt: string;
  source: RegulationSourceSummary;
}

export type RegulationSectionType = "chapter" | "article" | "clause" | string;

export interface RegulationSection {
  id: string;
  sectionType: RegulationSectionType;
  code: string;
  path: string[];
  titleAr: string | null;
  titleEn: string | null;
  textAr: string | null;
  textEn: string | null;
  position: number;
  parentSectionId: string | null;
  amendmentNoteAr: string | null;
  amendmentNoteEn: string | null;
}

export interface RegulationDocument {
  id: string;
  language: string;
  documentFormat: string;
  sourceUrl: string;
  sections: RegulationSection[];
}

export interface RegulationVersionDetail {
  versionId: string;
  versionLabel: string;
  status: string;
  officialCitation: string | null;
  contentHash: string;
  createdAt: string;
  source: RegulationSourceSummary;
  documents: RegulationDocument[];
}

export interface ApproveRegulationResult {
  versionId: string;
  status: string;
  approvedBy: string | null;
  approvedAt: string | null;
  sectionsEmbedded: number;
  sectionsFailed: number;
}

export interface RejectRegulationResult {
  versionId: string;
  status: string;
}
