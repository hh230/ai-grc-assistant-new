import type { Metadata } from "next";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { ScoreCards } from "@/components/dashboard/ScoreCards";
import { StatCards } from "@/components/dashboard/StatCards";
import { ExecutiveSummary } from "@/components/dashboard/ExecutiveSummary";
import { ActiveFrameworks } from "@/components/dashboard/ActiveFrameworks";
import { NeedsAttention } from "@/components/dashboard/NeedsAttention";
import { IntelligentInsights } from "@/components/dashboard/IntelligentInsights";
import { ComplianceProgress } from "@/components/dashboard/ComplianceProgress";
import { RiskDistribution } from "@/components/dashboard/RiskDistribution";
import { RecentAssessments } from "@/components/dashboard/RecentAssessments";
import { AiWorkspaceCard } from "@/components/dashboard/AiWorkspaceCard";
import { RecentActivities } from "@/components/dashboard/RecentActivities";
import { ReportsSection } from "@/components/dashboard/ReportsSection";
import { WorkspaceHub } from "@/components/dashboard/WorkspaceHub";
import { FavoritesPanel } from "@/components/dashboard/FavoritesPanel";

export const metadata: Metadata = {
  title: "Executive Dashboard · Rasheed",
};

export default function ExecutiveDashboardPage() {
  return (
    <>
      <PageHeader />

      <div className="space-y-7">
        {/* Overall Compliance & Risk scores */}
        <ScoreCards />

        {/* Headline KPIs */}
        <StatCards />

        {/* AI-generated narrative */}
        <ExecutiveSummary />

        {/* Active frameworks: NCA ECC · PDPL · ISO 27001 */}
        <ActiveFrameworks />

        {/* Band 2 — what needs a decision today, ranked danger-first */}
        <NeedsAttention />

        {/* Real-workspace signals — risks, documents, and analyses actually in this tenant's
            data, distinct from the illustrative bands above. Renders nothing when empty. */}
        <IntelligentInsights />

        {/* Band 3 — analytics & operational detail */}
        <div className="grid grid-cols-12 gap-5">
          <div className="col-span-12 lg:col-span-7">
            <ComplianceProgress />
          </div>
          <div className="col-span-12 lg:col-span-5">
            <RiskDistribution />
          </div>

          <div className="col-span-12 lg:col-span-7">
            <RecentAssessments />
          </div>
          <div className="col-span-12 lg:col-span-5">
            <AiWorkspaceCard />
          </div>

          <div className="col-span-12 lg:col-span-7">
            <RecentActivities />
          </div>
          <div className="col-span-12 lg:col-span-5">
            <ReportsSection />
          </div>
        </div>

        {/* Intelligent Workspace — Continue working / Quick Actions / Favorites
            (design proposal §9). Purely additive: extends the page, doesn't touch
            Bands 1-3 above. */}
        <div className="grid grid-cols-12 gap-5">
          <div className="col-span-12 lg:col-span-7">
            <WorkspaceHub />
          </div>
          <div className="col-span-12 lg:col-span-5">
            <FavoritesPanel />
          </div>
        </div>
      </div>
    </>
  );
}
