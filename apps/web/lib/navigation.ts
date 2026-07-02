import type { Route } from "next";
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
  label: string;
  href: Route;
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
  items: NavLink[];
}

export const PRIMARY_NAV: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { label: "Executive Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "AI Workspace", href: "/workspace", icon: Sparkles, badge: "New" },
      { label: "Missions", href: "/missions", icon: Workflow },
    ],
  },
  {
    label: "Governance",
    items: [
      { label: "Controls", href: "/controls", icon: ShieldCheck },
      { label: "Policies", href: "/policies", icon: FileText },
      { label: "Frameworks", href: "/frameworks", icon: Library },
    ],
  },
  {
    label: "Risk & Compliance",
    items: [
      { label: "Risk Register", href: "/risk-register", icon: TriangleAlert, badge: "7" },
      { label: "Assessments", href: "/assessments", icon: ClipboardList },
      { label: "Evidence", href: "/evidence", icon: FolderArchive },
      { label: "Reports", href: "/reports", icon: FileText },
    ],
  },
];

export const FOOTER_NAV: NavLink[] = [
  // Workspace administration is restricted to owners and admins (matches the server guard).
  { label: "Settings", href: "/settings", icon: Settings, requiredRoles: ["owner", "admin"] },
  { label: "Help & Support", href: "/help", icon: LifeBuoy },
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
