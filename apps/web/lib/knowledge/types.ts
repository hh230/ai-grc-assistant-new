/**
 * Domain types for the Knowledge Review Console (ADR 0067).
 *
 * These mirror grc-api's `ReviewQuestionView` — the REVIEWER's shape, which carries `whyWeAsk`.
 * The customer-facing `InterviewQuestionView` has no such field and is deliberately not modelled
 * here: this console is the only surface that shows it, and there is no type in `apps/web` that
 * could carry reviewer-only text into a customer's screen by accident.
 */

/** Where a question comes from. `clause` is optional because a model that does not know the
 * clause number must be able to say so rather than invent one. */
export interface KnowledgeReference {
  framework: string;
  clause?: string;
}

/** The schema's vocabulary (`release_questions_type_renderable`, migration 0007) — not a second
 * one invented here. Two vocabularies for one concept is a translation layer waiting to be written. */
export type QuestionType =
  | "boolean"
  | "enum"
  | "multi_select"
  | "numeric"
  | "date"
  | "text";
export type QuestionImportance = "critical" | "high" | "medium" | "low";

export interface ReviewQuestion {
  questionId: string;
  canonicalTextAr: string;
  type: QuestionType;
  options: string[];
  required: boolean;
  category: string;
  importance: QuestionImportance;
  references: KnowledgeReference[];
  /** Reviewer-only: the case for the question's existence. Never shown to a customer. */
  whyWeAsk: string;
  evidenceRequired: string[];
}

/**
 * The five states a release moves through. `released` means *eligible* to be activated — not live.
 * Exactly one release per industry is live at a time, and which one is a separate pointer.
 */
export type ReleaseStatus = "draft" | "in_review" | "approved" | "released" | "deprecated";

export interface KnowledgeRelease {
  id: string;
  industrySlug: string;
  version: number;
  status: ReleaseStatus;
  /** The three facts that make a release reproducible rather than merely explainable. */
  generatedByModel: string;
  promptVersion: string;
  generatorCommit: string;
  createdBy: string;
  approvedBy: string | null;
  approvedAt: string | null;
  releasedAt: string | null;
  questions: ReviewQuestion[] | null;
}

export interface Industry {
  slug: string;
  canonicalNameAr: string;
  status: "active" | "retired";
}

export interface ActivationRecord {
  releaseId: string;
  activatedBy: string;
  activatedAt: string;
  reason: string;
}

/**
 * What a write returned. `changed: false` is a success that changed nothing — every knowledge
 * write is idempotent, so approving twice is a no-op rather than an error, and the UI says so
 * instead of showing a failure.
 */
export interface KnowledgeOutcome {
  changed: boolean;
  event: string | null;
  data: Record<string, unknown>;
}

/**
 * An authored pack shipped with the deployment, before anyone imports it.
 *
 * `problem` is non-null when the file itself is unusable. Listed rather than hidden, so a broken
 * pack is fixed before somebody tries to deploy that sector.
 */
export interface AuthoredPack {
  industrySlug: string;
  canonicalNameAr: string;
  questionCount: number;
  authoredBy: string;
  problem: string | null;
}

/** The lifecycle actions a reviewer can take on a release. */
export type ReleaseAction = "submit" | "approve" | "reject" | "publish";
