"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import { Popover } from "@/components/ui/Popover";
import { useSession } from "@/components/auth/SessionProvider";
import { ORGANIZATIONS } from "@/lib/data";

/** Derive a 2-letter monogram from an organization name. */
function monogram(name: string): string {
  const words = name.trim().split(/\s+/);
  const letters = (words[0]?.[0] ?? "") + (words[1]?.[0] ?? words[0]?.[1] ?? "");
  return letters.toUpperCase() || "··";
}

export function OrgSwitcher() {
  const { user } = useSession();
  // The tenant is bound to the authenticated session; the active org reflects it.
  const activeOrg = ORGANIZATIONS.find((org) => org.name === user.organizationName);
  const initials = activeOrg?.initials ?? monogram(user.organizationName);
  const plan = activeOrg?.plan ?? "Enterprise";

  return (
    <Popover
      align="start"
      width={272}
      trigger={() => (
        <span className="flex h-9 items-center gap-2.5 rounded-lg border border-hairline bg-surface/60 pl-2 pr-2.5 transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent-soft text-2xs font-semibold text-accent-foreground">
            {initials}
          </span>
          <span className="hidden flex-col items-start leading-tight md:flex">
            <span className="text-xs font-medium text-foreground">{user.organizationName}</span>
            <span className="text-2xs text-foreground-muted">{plan}</span>
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 text-foreground-muted" strokeWidth={1.75} />
        </span>
      )}
    >
      <div className="px-2 py-1.5">
        <p className="px-2 py-1.5 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Active organization
        </p>
        <div className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent-soft text-2xs font-semibold text-accent-foreground">
            {initials}
          </span>
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-sm text-foreground">{user.organizationName}</span>
            <span className="block truncate text-2xs text-foreground-muted">
              {activeOrg?.region ?? "Tenant-bound session"}
            </span>
          </span>
          <Check className="h-4 w-4 text-accent-foreground" strokeWidth={2} />
        </div>
        <p className="px-2 pb-1 pt-2 text-2xs text-foreground-muted">
          Switching organizations requires signing in to that tenant.
        </p>
      </div>
    </Popover>
  );
}
