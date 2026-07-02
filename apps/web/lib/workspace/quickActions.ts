import { FileUp, TriangleAlert, FileText, Sparkles, FileBarChart, type LucideIcon } from "lucide-react";

export interface QuickAction {
  /** Key into the `workspace.quickActions` next-intl namespace. */
  key: string;
  icon: LucideIcon;
  href: string;
}

/** Shared across the command palette's empty state and the dashboard's Workspace Hub —
 *  one definition, two surfaces (V2-P3 design proposal §9's Workspace concept). */
export const QUICK_ACTIONS: QuickAction[] = [
  { key: "uploadDocument", icon: FileUp, href: "/upload" },
  { key: "newRisk", icon: TriangleAlert, href: "/risk-register" },
  { key: "newPolicy", icon: FileText, href: "/policies" },
  { key: "askAssistant", icon: Sparkles, href: "/workspace" },
  { key: "generateReport", icon: FileBarChart, href: "/reports" },
];
