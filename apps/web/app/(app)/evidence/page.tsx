import type { Metadata } from "next";
import { can } from "@/lib/auth/permissions";
import { requireSession } from "@/lib/auth/server";
import { EvidenceWorkspace } from "@/components/evidence/EvidenceWorkspace";

export const metadata: Metadata = {
  title: "Evidence · Sentinel GRC",
};

export default async function EvidencePage() {
  const session = await requireSession();
  const canCreate = can(session.roles, "create", "evidence");
  const canUpdate = can(session.roles, "update", "evidence");
  const canDelete = can(session.roles, "delete", "evidence");

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Risk &amp; Compliance
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Evidence</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          Collect and manage the artifacts that prove your controls are operating — tagged,
          version-controlled, and linked back to the controls they support.
        </p>
      </header>

      <EvidenceWorkspace canCreate={canCreate} canUpdate={canUpdate} canDelete={canDelete} />
    </div>
  );
}
