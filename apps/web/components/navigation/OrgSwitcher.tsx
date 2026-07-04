"use client";

import { useState } from "react";
import { Check, ChevronsUpDown, Loader2, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { Popover } from "@/components/ui/Popover";
import { useSession } from "@/components/auth/SessionProvider";
import { useOrganizations } from "@/hooks/useOrganizations";
import { switchOrganization } from "@/lib/organizations/client";
import { CreateOrganizationModal } from "@/components/navigation/CreateOrganizationModal";

/** Derive a 2-letter monogram from an organization name. */
function monogram(name: string): string {
  const words = name.trim().split(/\s+/);
  const letters = (words[0]?.[0] ?? "") + (words[1]?.[0] ?? words[0]?.[1] ?? "");
  return letters.toUpperCase() || "··";
}

export function OrgSwitcher() {
  const { user } = useSession();
  const t = useTranslations("orgSwitcher");
  const { data, isLoading } = useOrganizations();
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const organizations = data?.organizations ?? [];
  const initials = monogram(user.organizationName);

  async function handleSwitch(organizationId: string) {
    if (organizationId === user.organizationId || switchingId) return;
    setSwitchingId(organizationId);
    try {
      await switchOrganization(organizationId);
      window.location.reload();
    } catch {
      setSwitchingId(null);
    }
  }

  return (
    <>
      <Popover
        align="start"
        width={288}
        ariaLabel={t("menuLabel", { organization: user.organizationName })}
        trigger={() => (
          <span className="flex h-9 items-center gap-2.5 rounded-lg border border-hairline bg-surface/60 ps-2 pe-2.5 transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent-soft text-2xs font-semibold text-accent-foreground">
              {initials}
            </span>
            <span className="hidden flex-col items-start leading-tight md:flex">
              <span className="text-xs font-medium text-foreground">
                {user.organizationName}
              </span>
              <span className="text-2xs text-foreground-muted">{t("switcherTrigger")}</span>
            </span>
            <ChevronsUpDown className="h-3.5 w-3.5 text-foreground-muted" strokeWidth={1.75} />
          </span>
        )}
      >
        <div className="px-2 py-1.5">
          <p className="px-2 py-1.5 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
            {t("yourOrganizations")}
          </p>
          <div className="max-h-64 space-y-0.5 overflow-y-auto">
            {isLoading && (
              <div className="flex items-center gap-2 px-2 py-2 text-xs text-foreground-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />
                {t("loading")}
              </div>
            )}
            {!isLoading && organizations.length === 0 && (
              <p className="px-2 py-2 text-xs text-foreground-muted">{t("noOrganizations")}</p>
            )}
            {organizations.map((org) => {
              const active = org.id === user.organizationId;
              return (
                <button
                  key={org.id}
                  type="button"
                  onClick={() => handleSwitch(org.id)}
                  disabled={switchingId !== null}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-start transition-colors duration-150 hover:bg-surface disabled:cursor-wait"
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent-soft text-2xs font-semibold text-accent-foreground">
                    {monogram(org.name)}
                  </span>
                  <span className="min-w-0 flex-1 leading-tight">
                    <span className="block truncate text-sm text-foreground">{org.name}</span>
                    <span className="block truncate text-2xs text-foreground-muted">
                      {org.industry}
                    </span>
                  </span>
                  {switchingId === org.id ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-foreground-muted" strokeWidth={2} />
                  ) : (
                    active && <Check className="h-4 w-4 shrink-0 text-accent-foreground" strokeWidth={2} />
                  )}
                </button>
              );
            })}
          </div>
          <div className="mt-1 border-t border-hairline pt-1">
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-start text-sm text-foreground-secondary transition-colors duration-150 hover:bg-surface hover:text-foreground"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-dashed border-hairline-strong">
                <Plus className="h-4 w-4" strokeWidth={1.75} />
              </span>
              {t("addOrganization")}
            </button>
          </div>
        </div>
      </Popover>

      <CreateOrganizationModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => window.location.reload()}
      />
    </>
  );
}
