/**
 * Maps a question's raw option codes to the shared i18n namespace that translates them
 * (`discoveryInterview.options.*`). A few option scales are reused across several questions (the
 * 5-level maturity scale, for instance), so this is a small lookup rather than one namespace per
 * question. Presentation-only — it knows nothing about how the engine derived these options.
 */

const MATURITY_SCALE_QUESTIONS = new Set([
  "q:org_structure_state",
  "q:policy_state",
  "q:risk_register_state",
  "q:internal_audit_state",
  "q:tech_team_maturity",
]);

export function optionsNamespaceFor(questionId: string): string {
  if (questionId === "q:primary_activity") return "discoveryInterview.options.primaryActivity";
  if (questionId === "q:execution_capacity") return "discoveryInterview.options.executionCapacity";
  if (questionId === "q:cloud_data_residency_controlled") return "discoveryInterview.options.triState";
  if (questionId === "q:held_licenses") return "discoveryInterview.options.licenses";
  if (MATURITY_SCALE_QUESTIONS.has(questionId)) return "discoveryInterview.options.maturityScale";
  return "discoveryInterview.options.generic";
}
