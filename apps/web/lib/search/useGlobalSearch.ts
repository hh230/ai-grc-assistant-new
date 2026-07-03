"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { useDocuments } from "@/hooks/useDocuments";
import { useAnalyses } from "@/hooks/useAnalyses";
import { usePolicies } from "@/hooks/usePolicies";
import { useRisks } from "@/hooks/useRisks";
import { useEvidence } from "@/hooks/useEvidence";
import { REPORT_KINDS } from "@/lib/reports/types";
import type { SearchEntityType, SearchResultItem } from "./types";

const MAX_PER_GROUP = 5;
const MAX_RECENT = 4;

function matches(query: string, ...fields: Array<string | undefined>): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return fields.some((field) => field?.toLowerCase().includes(q));
}

export interface SearchResultGroup {
  type: SearchEntityType;
  items: SearchResultItem[];
}

export interface UseGlobalSearchResult {
  /** Grouped, filtered results — empty until `query` is non-empty. */
  groups: SearchResultGroup[];
  totalCount: number;
  isLoading: boolean;
  isError: boolean;
  /** Most recently updated documents/analyses — shown when `query` is empty, so the
   *  palette is useful the moment it opens (matches the "recent files" convention in
   *  Linear/VS Code's own command palettes). */
  recentDocuments: SearchResultItem[];
  recentAnalyses: SearchResultItem[];
}

/**
 * Runs Global Search over the same real, tenant-scoped data every other workspace page
 * already fetches via TanStack Query — no separate index, no fake data. See
 * `lib/search/types.ts` for why this is a drop-in seam for a future `search_workspace.v1`
 * Tool rather than a permanent client-side implementation.
 */
export function useGlobalSearch(query: string): UseGlobalSearchResult {
  const documents = useDocuments();
  const analyses = useAnalyses();
  const policies = usePolicies();
  const risks = useRisks();
  const evidence = useEvidence({});
  const tCategory = useTranslations("documentCategories");
  const tReportKinds = useTranslations("reportsWorkspace.kinds");

  const groups = useMemo<SearchResultGroup[]>(() => {
    const q = query.trim();
    if (!q) return [];

    const documentItems: SearchResultItem[] = (documents.data ?? [])
      .filter((doc) => matches(q, doc.fileName, tCategory(doc.category)))
      .slice(0, MAX_PER_GROUP)
      .map((doc) => ({
        id: doc.id,
        type: "document" as const,
        title: doc.fileName,
        subtitle: tCategory(doc.category),
        href: `/analysis?doc=${doc.id}`,
      }));

    const analysisItems: SearchResultItem[] = (analyses.data ?? [])
      .filter((a) => matches(q, a.title, a.fileName))
      .slice(0, MAX_PER_GROUP)
      .map((a) => ({
        id: a.documentId,
        type: "analysis" as const,
        title: a.title,
        subtitle: `v${a.version}`,
        href: `/analysis?doc=${a.documentId}`,
      }));

    const policyItems: SearchResultItem[] = (policies.data ?? [])
      .filter((p) => matches(q, p.title, p.summary, p.ownerName))
      .slice(0, MAX_PER_GROUP)
      .map((p) => ({
        id: p.id,
        type: "policy" as const,
        title: p.title,
        subtitle: p.ownerName,
        href: `/policies?open=${p.id}`,
      }));

    const riskItems: SearchResultItem[] = (risks.data ?? [])
      .filter((r) => matches(q, r.title, r.ownerName))
      .slice(0, MAX_PER_GROUP)
      .map((r) => ({
        id: r.id,
        type: "risk" as const,
        title: r.title,
        subtitle: r.ownerName,
        href: `/risk-register?open=${r.id}`,
      }));

    const evidenceItems: SearchResultItem[] = (evidence.data ?? [])
      .filter((e) => matches(q, e.title, e.description, ...e.tags))
      .slice(0, MAX_PER_GROUP)
      .map((e) => ({
        id: e.id,
        type: "evidence" as const,
        title: e.title,
        subtitle: e.currentVersion?.fileName,
        href: `/evidence?open=${e.id}`,
      }));

    const reportItems: SearchResultItem[] = REPORT_KINDS.filter((kind) =>
      matches(q, tReportKinds(`${kind}.title`), tReportKinds(`${kind}.subtitle`)),
    ).map((kind) => ({
      id: kind,
      type: "report" as const,
      title: tReportKinds(`${kind}.title`),
      subtitle: tReportKinds(`${kind}.subtitle`),
      href: `/reports?kind=${kind}`,
    }));

    return [
      { type: "document" as const, items: documentItems },
      { type: "analysis" as const, items: analysisItems },
      { type: "policy" as const, items: policyItems },
      { type: "risk" as const, items: riskItems },
      { type: "evidence" as const, items: evidenceItems },
      { type: "report" as const, items: reportItems },
    ].filter((group) => group.items.length > 0);
  }, [query, documents.data, analyses.data, policies.data, risks.data, evidence.data, tCategory, tReportKinds]);

  const recentDocuments = useMemo<SearchResultItem[]>(
    () =>
      [...(documents.data ?? [])]
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
        .slice(0, MAX_RECENT)
        .map((doc) => ({
          id: doc.id,
          type: "document" as const,
          title: doc.fileName,
          subtitle: tCategory(doc.category),
          href: `/analysis?doc=${doc.id}`,
        })),
    [documents.data, tCategory],
  );

  const recentAnalyses = useMemo<SearchResultItem[]>(
    () =>
      [...(analyses.data ?? [])]
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
        .slice(0, MAX_RECENT)
        .map((a) => ({
          id: a.documentId,
          type: "analysis" as const,
          title: a.title,
          subtitle: `v${a.version}`,
          href: `/analysis?doc=${a.documentId}`,
        })),
    [analyses.data],
  );

  const isLoading =
    Boolean(query.trim()) &&
    (documents.isLoading ||
      analyses.isLoading ||
      policies.isLoading ||
      risks.isLoading ||
      evidence.isLoading);
  const isError =
    documents.isError || analyses.isError || policies.isError || risks.isError || evidence.isError;
  const totalCount = groups.reduce((sum, group) => sum + group.items.length, 0);

  return { groups, totalCount, isLoading, isError, recentDocuments, recentAnalyses };
}
