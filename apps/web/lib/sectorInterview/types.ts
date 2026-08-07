/**
 * The customer's side of a Knowledge Pack (ADR 0067).
 *
 * These questions were written by Claude, reviewed by a human, published, and then deliberately
 * ACTIVATED for this sector. Nothing else reaches a customer — a draft cannot, and a published
 * version nobody activated cannot either.
 *
 * Note what is absent: `whyWeAsk`. The reviewer's case for a question is not a field this type has,
 * so no customer-facing code can render it by accident.
 */

export interface SectorQuestion {
  questionId: string;
  canonicalTextAr: string;
  type: "boolean" | "enum" | "multi_select" | "numeric" | "date" | "text";
  options: string[];
  required: boolean;
  category: string;
  importance: "critical" | "high" | "medium" | "low";
  references: { framework: string; clause?: string }[];
  evidenceRequired: string[];
}

export interface SectorInterview {
  /**
   * `opened` — a new assessment, citing the release live at that moment.
   * `already_open` — this session's assessment, resumed with the release it cites.
   * `no_sector_pack` — the sector has nothing activated. A NORMAL answer, not a failure: most
   *   sectors have no published pack yet, and an organization must still be able to finish.
   */
  status: "opened" | "already_open" | "no_sector_pack";
  assessmentId: string | null;
  completed: boolean;
  /** Present when RESUMING. A returning customer holds no session id, and the plan is generated
   * from the session — so the answer carries it back. */
  sourceSessionId: string | null;
  release: {
    releaseId: string;
    industrySlug: string;
    version: number;
    questions: SectorQuestion[];
  } | null;
}

export interface SectorAnswer {
  releaseId: string;
  questionId: string;
  answer: unknown;
}
