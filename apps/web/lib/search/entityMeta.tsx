import {
  FileText,
  ClipboardCheck,
  FileCheck2,
  TriangleAlert,
  FolderArchive,
  FileBarChart,
  type LucideIcon,
} from "lucide-react";
import type { SearchEntityType } from "./types";

/** Icon per entity type — reuses the same icon already used for that entity type
 *  elsewhere in the app (RecentActivities' `kindMeta`, the sidebar nav) so a result
 *  row looks like a natural extension of the existing product, not a new vocabulary. */
export const ENTITY_ICON: Record<SearchEntityType, LucideIcon> = {
  document: FileText,
  analysis: ClipboardCheck,
  policy: FileCheck2,
  risk: TriangleAlert,
  evidence: FolderArchive,
  report: FileBarChart,
};
