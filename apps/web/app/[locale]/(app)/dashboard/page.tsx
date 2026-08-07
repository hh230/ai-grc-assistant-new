import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getActor } from "@/lib/auth/actor";
import { requireSession } from "@/lib/auth/server";
import { pageTitle } from "@/lib/pageMetadata";
import { getProgramStatus } from "@/lib/dashboard/programStatus";
import { getGovernanceActivity } from "@/lib/dashboard/governanceActivity";
import { ProgramStatus } from "@/components/dashboard/ProgramStatus";
import { GovernanceMaturity } from "@/components/dashboard/GovernanceMaturity";
import { WhatToDoNext } from "@/components/dashboard/WhatToDoNext";
import { GovernanceActivity } from "@/components/dashboard/GovernanceActivity";
import { EvidenceCoverage } from "@/components/dashboard/EvidenceCoverage";

export async function generateMetadata(): Promise<Metadata> {
  return pageTitle("programStatus.title");
}

/**
 * The home page — the governance program's dashboard (CLAUDE.md §3 pillar 10).
 *
 * Five sections, in the order a customer reasons: where am I → where do I stand → what do I do
 * next → what has happened → what can I prove. A score is never the first thing, because a score
 * is not a thing you can act on.
 *
 * What this page is NOT any more: a document-analysis dashboard. The compliance and risk averages
 * derived from reading uploads, and the narrative built on top of them, measured the documents a
 * customer had uploaded rather than the organization — and led the page. They now live where
 * documents live, per document, never aggregated into a verdict about the organization.
 */
export default async function GovernanceHomePage() {
  await requireSession();
  const actor = await getActor();
  if (!actor) redirect("/login");

  const status = await getProgramStatus(actor);

  // With no program the status card IS the page. A dashboard of zeroes is not an empty dashboard;
  // it is a customer who has not started, and the only useful thing to show them is the way in.
  if (status.state === "none" || status.plan === null) {
    return <ProgramStatus status={status} />;
  }

  const activity = await getGovernanceActivity(actor, status);

  return (
    <div className="space-y-5">
      <ProgramStatus status={status} />
      <GovernanceMaturity actor={actor} plan={status.plan} />
      <WhatToDoNext plan={status.plan} />
      <GovernanceActivity events={activity} />
      <EvidenceCoverage actor={actor} />
    </div>
  );
}
