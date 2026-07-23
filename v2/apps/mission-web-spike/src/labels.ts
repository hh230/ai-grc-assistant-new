// Shared product-language labels — the ONE place raw Core ids become the words the user reads.
// V1 Polish: the Core status/type ids leaked to the UI (a generic `_`→titlecase produced "Executing",
// "Awaiting Approval", "Iso Controls"). Those are implementation words; the product speaks GRC. Every
// place that shows a status or a type routes through here, so the wording is fixed once and stays
// consistent across the Dashboard, Missions, the Work Surface, and Decisions.

const STATUS_LABELS: Record<string, string> = {
  created: "Created",
  planned: "Planned",
  executing: "Running", // the user's word for a mission in progress (not the Core's "executing")
  awaiting_approval: "Awaiting decision", // a decision is waiting — never "Approval" (that word retired)
  resumed: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
  archived: "Archived",
};

const TYPE_LABELS: Record<string, string> = {
  gap_assessment: "Gap Assessment",
  risk_assessment: "Risk Assessment",
  vendor_review: "Vendor Review",
  policy_generator: "Policy Generator",
  iso_controls: "ISO Controls", // not "Iso Controls" — the acronym the compliance officer actually uses
  simple_question: "Ask",
};

// The framework a mission type assesses against. Only the two types that genuinely run against a
// standard have one; the rest return null and show no framework (we show the truth, we don't invent a
// picker — the system has exactly one framework as data today). Answers the user's real question at
// creation: "What will this mission assess against?"
const TYPE_FRAMEWORK: Record<string, string> = {
  gap_assessment: "ISO/IEC 27001:2022",
  iso_controls: "ISO/IEC 27001:2022",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? titleCase(status);
}

export function typeLabel(type: string): string {
  return TYPE_LABELS[type] ?? titleCase(type);
}

export function frameworkFor(type: string): string | null {
  return TYPE_FRAMEWORK[type] ?? null;
}

function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
