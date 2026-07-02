/**
 * Static, typed demo content for the Executive Dashboard.
 *
 * This is NOT a mock API: there is no fetch, no route handler, and no network.
 * These are compile-time constants used purely to render the presentation layer
 * for the investor demo. When the backend lands, components consume the same
 * shapes from the Services/Tools layer instead.
 */

export type Trend = "up" | "down" | "flat";

export type FrameworkStatus = "compliant" | "in_progress" | "at_risk";

export interface Organization {
  id: string;
  name: string;
  plan: string;
  region: string;
  initials: string;
}

export interface ActiveFramework {
  id: string;
  code: string;
  name: string;
  authority: string;
  coverage: number;
  controls: number;
  controlsMet: number;
  status: FrameworkStatus;
  region: string;
}

export interface Assessment {
  id: string;
  name: string;
  framework: string;
  owner: string;
  status: "completed" | "in_review" | "in_progress";
  score: number | null;
  updated: string;
}

export interface ProgressItem {
  label: string;
  value: number;
  target: number;
  delta: number;
}

export interface RiskSlice {
  /** English fallback label — kept for non-translated contexts. */
  label: string;
  /** Key into the `dashboard.riskDistribution.categories` next-intl namespace. */
  labelKey: string;
  value: number;
  tone: "accent" | "warning" | "danger" | "success" | "neutral";
}

export interface Activity {
  id: string;
  actor: string;
  action: string;
  target: string;
  kind: "assessment" | "evidence" | "risk" | "policy" | "ai" | "report";
  time: string;
}

export interface ReportItem {
  id: string;
  name: string;
  type: string;
  period: string;
  status: "ready" | "scheduled" | "generating";
  updated: string;
}

export const ORGANIZATIONS: Organization[] = [
  {
    id: "acme",
    name: "Acme Financial Group",
    plan: "Enterprise",
    region: "KSA · Riyadh",
    initials: "AF",
  },
  { id: "nuevo", name: "Nuevo Bank", plan: "Enterprise", region: "UAE · Dubai", initials: "NB" },
  {
    id: "halcyon",
    name: "Halcyon Health",
    plan: "Business",
    region: "KSA · Jeddah",
    initials: "HH",
  },
];

/** Stable default so consumers never index into a possibly-empty array. */
export const DEFAULT_ORGANIZATION: Organization = ORGANIZATIONS[0] ?? {
  id: "acme",
  name: "Acme Financial Group",
  plan: "Enterprise",
  region: "KSA · Riyadh",
  initials: "AF",
};

export const CURRENT_USER = {
  name: "Mohammed Al-Sayyar",
  role: "Chief Risk & Compliance Officer",
  email: "m.alsayyar@acmefin.com",
  initials: "MA",
};

export const COMPLIANCE_SCORE = {
  value: 87,
  target: 95,
  trend: "up" as Trend,
  delta: 3.2,
  caption: "Weighted across 6 active frameworks",
};

export const RISK_SCORE = {
  value: 34,
  band: "Moderate",
  trend: "down" as Trend,
  delta: 5.0,
  caption: "Residual risk index · lower is better",
};

export const KPIS = [
  {
    labelKey: "frameworksActive",
    label: "Frameworks active",
    value: "6",
    trend: "flat" as Trend,
    delta: 0,
  },
  {
    labelKey: "controlsMonitored",
    label: "Controls monitored",
    value: "1,248",
    trend: "up" as Trend,
    delta: 4.1,
  },
  {
    labelKey: "openFindings",
    label: "Open findings",
    value: "23",
    trend: "down" as Trend,
    delta: 12.0,
  },
  {
    labelKey: "aiReviews",
    label: "AI reviews this month",
    value: "412",
    trend: "up" as Trend,
    delta: 28.0,
  },
];

/**
 * Headline/body/footer live in the `dashboard.executiveSummary` next-intl namespace
 * (narrative text, not data) — this keeps only the stat values, keyed for translated
 * labels via `dashboard.executiveSummary.stats.<key>`.
 */
export const EXECUTIVE_SUMMARY_STATS = [
  { key: "auditReadyFrameworks", value: "2 of 6" },
  { key: "evidenceFreshness", value: "94%" },
  { key: "meanTimeToRemediate", value: "11 days" },
  { key: "nextExternalAudit", value: "Sep 2026" },
];

export const ACTIVE_FRAMEWORKS: ActiveFramework[] = [
  {
    id: "nca_ecc",
    code: "NCA ECC",
    name: "Essential Cybersecurity Controls",
    authority: "National Cybersecurity Authority",
    coverage: 91,
    controls: 114,
    controlsMet: 104,
    status: "compliant",
    region: "Saudi Arabia",
  },
  {
    id: "pdpl",
    code: "PDPL",
    name: "Personal Data Protection Law",
    authority: "SDAIA",
    coverage: 78,
    controls: 73,
    controlsMet: 57,
    status: "in_progress",
    region: "Saudi Arabia",
  },
  {
    id: "iso_27001",
    code: "ISO 27001",
    name: "Information Security Management",
    authority: "ISO/IEC",
    coverage: 84,
    controls: 93,
    controlsMet: 78,
    status: "in_progress",
    region: "International",
  },
];

export const RECENT_ASSESSMENTS: Assessment[] = [
  {
    id: "a1",
    name: "NCA ECC — Annual Control Review",
    framework: "NCA ECC",
    owner: "S. Rahman",
    status: "completed",
    score: 91,
    updated: "2h ago",
  },
  {
    id: "a2",
    name: "ISO 27001 — Statement of Applicability",
    framework: "ISO 27001",
    owner: "L. Haddad",
    status: "in_review",
    score: 84,
    updated: "Yesterday",
  },
  {
    id: "a3",
    name: "PDPL — Data Processing Impact",
    framework: "PDPL",
    owner: "N. Aziz",
    status: "in_progress",
    score: null,
    updated: "2d ago",
  },
  {
    id: "a4",
    name: "SAMA CSF — Third-Party Risk",
    framework: "SAMA CSF",
    owner: "K. Osman",
    status: "completed",
    score: 88,
    updated: "4d ago",
  },
  {
    id: "a5",
    name: "NIST CSF — Detect & Respond",
    framework: "NIST CSF",
    owner: "T. Mansour",
    status: "in_review",
    score: 79,
    updated: "5d ago",
  },
];

export const COMPLIANCE_PROGRESS: ProgressItem[] = [
  { label: "NCA ECC", value: 91, target: 95, delta: 2.4 },
  { label: "ISO 27001", value: 84, target: 90, delta: 3.1 },
  { label: "PDPL", value: 78, target: 90, delta: 5.7 },
  { label: "SAMA CSF", value: 88, target: 92, delta: 1.2 },
  { label: "NIST CSF", value: 81, target: 88, delta: 2.0 },
];

export const RISK_DISTRIBUTION: RiskSlice[] = [
  { label: "Cybersecurity", labelKey: "cybersecurity", value: 32, tone: "accent" },
  { label: "Data Privacy", labelKey: "dataPrivacy", value: 24, tone: "warning" },
  { label: "Third-Party", labelKey: "thirdParty", value: 18, tone: "danger" },
  { label: "Operational", labelKey: "operational", value: 15, tone: "success" },
  { label: "Regulatory", labelKey: "regulatory", value: 11, tone: "neutral" },
];

export const RECENT_ACTIVITIES: Activity[] = [
  {
    id: "e1",
    actor: "Compliance Agent",
    action: "completed assessment",
    target: "NCA ECC — Annual Control Review",
    kind: "assessment",
    time: "2h ago",
  },
  {
    id: "e2",
    actor: "S. Rahman",
    action: "approved control sign-off for",
    target: "Access Management (AC-2)",
    kind: "policy",
    time: "3h ago",
  },
  {
    id: "e3",
    actor: "Risk Agent",
    action: "flagged a high finding on",
    target: "Third-Party Data Transfers",
    kind: "risk",
    time: "5h ago",
  },
  {
    id: "e4",
    actor: "AI Orchestrator",
    action: "analyzed 18 evidence artifacts for",
    target: "ISO 27001 SoA",
    kind: "ai",
    time: "Yesterday",
  },
  {
    id: "e5",
    actor: "L. Haddad",
    action: "uploaded evidence to",
    target: "Encryption at Rest (A.10)",
    kind: "evidence",
    time: "Yesterday",
  },
  {
    id: "e6",
    actor: "Report Agent",
    action: "generated",
    target: "Board Risk Summary — Q2",
    kind: "report",
    time: "2d ago",
  },
];

export const REPORTS: ReportItem[] = [
  {
    id: "r1",
    name: "Board Risk & Compliance Summary",
    type: "Executive",
    period: "Q2 2026",
    status: "ready",
    updated: "2d ago",
  },
  {
    id: "r2",
    name: "NCA ECC Attestation Pack",
    type: "Regulatory",
    period: "2026",
    status: "ready",
    updated: "4d ago",
  },
  {
    id: "r3",
    name: "PDPL Data Protection Impact Assessment",
    type: "Privacy",
    period: "Q3 2026",
    status: "generating",
    updated: "1h ago",
  },
  {
    id: "r4",
    name: "ISO 27001 Statement of Applicability",
    type: "Audit",
    period: "2026",
    status: "scheduled",
    updated: "Sep 1",
  },
];

export const NOTIFICATIONS = [
  {
    id: "n1",
    title: "High-risk finding requires review",
    detail: "Third-Party Data Transfers · Risk Agent",
    time: "5h ago",
    unread: true,
    tone: "danger" as const,
  },
  {
    id: "n2",
    title: "Assessment ready for approval",
    detail: "ISO 27001 — Statement of Applicability",
    time: "Yesterday",
    unread: true,
    tone: "accent" as const,
  },
  {
    id: "n3",
    title: "PDPL DPIA generation in progress",
    detail: "Estimated completion in ~20 min",
    time: "1h ago",
    unread: false,
    tone: "neutral" as const,
  },
];
