// The 6 Mission types the user can start (product labels for the type picker). The ids match the
// backend Mission Catalog; the product shows the names, not the ids. "Ask" is the simple-question type.
export interface MissionTypeChoice {
  id: string;
  label: string;
  blurb: string;
}

export const MISSION_TYPES: MissionTypeChoice[] = [
  { id: "gap_assessment", label: "Gap Assessment", blurb: "Where your evidence meets a framework — and where it gaps." },
  { id: "risk_assessment", label: "Risk Assessment", blurb: "Identify and score risks for a scope." },
  { id: "iso_controls", label: "ISO Controls", blurb: "Work through the ISO 27001 controls for a scope." },
  { id: "policy_generator", label: "Policy Generator", blurb: "Draft a policy grounded in your context." },
  { id: "vendor_review", label: "Vendor Review", blurb: "Assess a third party against your requirements." },
  { id: "simple_question", label: "Ask", blurb: "A grounded question against your knowledge." },
];
