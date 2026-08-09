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

/**
 * One choice. `value` is what an answer records; `label` is what a person reads.
 *
 * They are the same string for every question authored before ADR 0068, and different only where a
 * question DECLARES an engine signal — there the value is a stable `option_id`, so that revising
 * the Arabic wording or adding a translation cannot move a compliance decision. Keeping both here,
 * rather than a bare string, is what stops the two cases needing two code paths.
 */
export interface SectorOption {
  value: string;
  label: string;
}

export interface SectorQuestion {
  questionId: string;
  canonicalTextAr: string;
  type: "boolean" | "enum" | "multi_select" | "numeric" | "date" | "text";
  options: SectorOption[];
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
  /**
   * What this assessment already holds, keyed by question id — the answers as the DATABASE has
   * them, not as any browser remembers them. A customer resumes from this, which is why it travels
   * with the interview rather than being fetched separately: an interview and what has been
   * answered in it are one fact.
   */
  answers: Record<string, unknown>;
}

export interface SectorAnswer {
  releaseId: string;
  questionId: string;
  answer: unknown;
}
