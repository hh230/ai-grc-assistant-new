import type { Metadata } from "next";
import { can } from "@/lib/auth/permissions";
import { requireSession } from "@/lib/auth/server";
import { RiskRegister } from "@/components/risk/RiskRegister";

export const metadata: Metadata = {
  title: "Risk Register · Sentinel GRC",
};

export default async function RiskRegisterPage() {
  const session = await requireSession();
  const permissions = {
    canCreate: can(session.roles, "create", "risk"),
    canUpdate: can(session.roles, "update", "risk"),
    canAccept: can(session.roles, "approve", "risk"),
    canDelete: can(session.roles, "delete", "risk"),
  };

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Risk &amp; Compliance
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          Risk Register
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          Identify, score, and track risks on a 5×5 matrix — with mitigating controls, residual
          scoring, and ownership. Accepting a risk is a human-gated decision.
        </p>
      </header>

      <RiskRegister {...permissions} />
    </div>
  );
}
