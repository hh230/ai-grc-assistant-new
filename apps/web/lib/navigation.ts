import {
  LayoutDashboard,
  ShieldCheck,
  ClipboardList,
  TriangleAlert,
  Library,
  FileText,
  FolderArchive,
  Sparkles,
  Workflow,
  Settings,
  LifeBuoy,
  Radar,
  Bot,
  type LucideIcon,
} from "lucide-react";
import type { UserRole } from "@/lib/auth/roles";
import { can, type Action, type ResourceType } from "@/lib/auth/permissions";

/**
 * Single source of truth for the workspace navigation (CLAUDE.md §21/§22 —
 * no magic route strings scattered across the UI). The Sidebar renders these,
 * and each `href` maps to a real route under `app/`. P1 ships the shell only:
 * destinations resolve to placeholder pages until later roadmap phases.
 */

export interface NavLink {
  /** English fallback label — kept for non-translated contexts (metadata, tests). */
  label: string;
  /** Key into the `nav.items` next-intl namespace (messages/{locale}.json); Sidebar
   * renders `t(labelKey)` so nav copy is locale-aware. */
  labelKey: string;
  /**
   * Locale-agnostic logical path (e.g. "/dashboard") — rendered through `@/i18n/navigation`'s
   * `Link`, which prefixes the current locale. Typed as `string`, not Next's `Route` brand:
   * `typedRoutes` validates against the literal `/[locale]/...` file-system routes, which
   * would force every nav href to be written with a hardcoded locale segment.
   */
  href: string;
  icon: LucideIcon;
  /** Small count/status pill (e.g. "7", "New"). Presentational only in P1. */
  badge?: string;
  /** Coarse role gate — item is hidden unless the user holds one of these roles. */
  requiredRoles?: UserRole[];
  /** Fine-grained gate — item is hidden unless the user can perform this on the resource. */
  requiredPermission?: { action: Action; resource: ResourceType };
}

export interface NavGroup {
  label: string;
  /** Key into the `nav.groups` next-intl namespace. */
  labelKey: string;
  items: NavLink[];
}

export const PRIMARY_NAV: NavGroup[] = [
  {
    label: "Overview",
    labelKey: "overview",
    items: [
      {
        label: "Executive Dashboard",
        labelKey: "dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
      },
      {
        label: "AI Assistant",
        labelKey: "aiAssistant",
        href: "/workspace",
        icon: Sparkles,
        badge: "New",
      },
      { label: "Missions", labelKey: "missions", href: "/missions", icon: Workflow },
    ],
  },
  {
    label: "Governance",
    labelKey: "governance",
    items: [
      { label: "Controls", labelKey: "controls", href: "/controls", icon: ShieldCheck },
      { label: "Policies", labelKey: "policies", href: "/policies", icon: FileText },
      {
        label: "Policy Intelligence",
        labelKey: "policyIntelligence",
        href: "/policy-intelligence",
        icon: Radar,
        requiredPermission: { action: "read", resource: "policy" },
      },
      { label: "Frameworks", labelKey: "frameworks", href: "/frameworks", icon: Library },
    ],
  },
  {
    label: "Risk & Compliance",
    labelKey: "riskCompliance",
    items: [
      {
        label: "Risk Register",
        labelKey: "riskRegister",
        href: "/risk-register",
        icon: TriangleAlert,
        badge: "7",
      },
      {
        label: "Assessments",
        labelKey: "assessments",
        href: "/assessments",
        icon: ClipboardList,
      },
      { label: "Evidence", labelKey: "evidence", href: "/evidence", icon: FolderArchive },
      { label: "Reports", labelKey: "reports", href: "/reports", icon: FileText },
    ],
  },
];

export const FOOTER_NAV: NavLink[] = [
  // Admin-only (matches the server guard on the page itself — CLAUDE.md §20).
  {
    label: "AI Worker",
    labelKey: "aiWorker",
    href: "/ai-worker",
    icon: Bot,
    requiredRoles: ["owner", "admin"],
  },
  // Workspace administration is restricted to owners and admins (matches the server guard).
  {
    label: "Settings",
    labelKey: "settings",
    href: "/settings",
    icon: Settings,
    requiredRoles: ["owner", "admin"],
  },
  { label: "Help & Support", labelKey: "help", href: "/help", icon: LifeBuoy },
];

/**
 * Active-state matcher. The dashboard ("/dashboard") must match exactly so it does not
 * light up on every route; section roots match themselves and any nested path.
 */
export function isNavItemActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Whether the given roles satisfy an item's role + permission gates (default allow). */
export function canSeeNavItem(item: NavLink, roles: readonly UserRole[]): boolean {
  if (item.requiredRoles && !item.requiredRoles.some((role) => roles.includes(role))) {
    return false;
  }
  if (
    item.requiredPermission &&
    !can(roles, item.requiredPermission.action, item.requiredPermission.resource)
  ) {
    return false;
  }
  return true;
}
