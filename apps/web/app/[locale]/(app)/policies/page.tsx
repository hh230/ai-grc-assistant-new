import type { Metadata } from "next";
import { can } from "@/lib/auth/permissions";
import { requireSession } from "@/lib/auth/server";
import { PoliciesWorkspace } from "@/components/policies/PoliciesWorkspace";

export const metadata: Metadata = {
  title: "Policies · Sentinel GRC",
};

export default async function PoliciesPage() {
  const session = await requireSession();
  const permissions = {
    canCreate: can(session.roles, "create", "policy"),
    canUpdate: can(session.roles, "update", "policy"),
    canPublish: can(session.roles, "publish", "policy"),
    canDelete: can(session.roles, "delete", "policy"),
  };

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Governance
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Policies</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          Author policies, map them to controls, and move them through review to publication.
          Publishing is a human-gated action restricted to owners, admins, and compliance managers.
        </p>
      </header>

      <PoliciesWorkspace {...permissions} />
    </div>
  );
}
