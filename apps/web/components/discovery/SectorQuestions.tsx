"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowLeft, ArrowRight, Check, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { saveSectorAnswer, submitSectorAnswers } from "@/lib/sectorInterview/client";
import type { SectorInterview, SectorQuestion } from "@/lib/sectorInterview/types";

/**
 * The sector stage of the interview — the far end of the Knowledge Pack loop.
 *
 * Every question here was written by a model, reviewed by a person, published, and then
 * deliberately activated for this sector. Nothing else can appear: a draft cannot reach this
 * screen, and neither can a published version nobody activated.
 *
 * Rendered in the canonical Arabic regardless of interface language, because that is the text a
 * human approved. Translations are an independent, separately-reviewed layer (ADR 0067); showing a
 * machine rendering of an approved question would mean the customer answered something no reviewer
 * ever saw.
 *
 * Asked ONE AT A TIME. The set is fixed the moment it opens — no answer changes which question
 * comes next — so this is not adaptivity, it is attention: twenty-two questions on one page is a
 * form somebody skims, and each of these deserves to be read. The count comes from the release, so
 * a pack with fifteen questions asks fifteen; nothing here knows how many there are.
 *
 * Every answer is saved as it is given, and the initial values are the ones the DATABASE holds —
 * `interview.answers`, not anything this component remembers. Asking one question at a time makes
 * an interview long, and a long interview crosses a closed laptop, a dead battery, an interruption.
 * The rule that follows: an answer that exists only in React state is an answer not yet given.
 */
export function SectorQuestions({
  interview,
  onDone,
  onError,
}: {
  interview: SectorInterview;
  onDone: () => void;
  onError: (message: string) => void;
}) {
  const t = useTranslations("sectorInterview");
  // Seeded from the database. A customer resuming at question nine sees the eight they answered,
  // because this component was never the thing holding them.
  const [values, setValues] = useState<Record<string, unknown>>(interview.answers);
  const [index, setIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // Saves run one after another rather than concurrently. Two answers given quickly are two
  // requests, and out of order the earlier value would land last and win — the customer would see
  // one thing and the database would hold another.
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  const release = interview.release;
  if (!release || !interview.assessmentId) return null;

  const questions = release.questions;
  const question = questions[index];
  if (!question) return null;
  const isLast = index === questions.length - 1;

  /** A multi-select is answered once ANY box is ticked; an empty array is still unanswered. */
  const unanswered = (q: SectorQuestion): boolean => {
    const answer = values[q.questionId];
    if (Array.isArray(answer)) return answer.length === 0;
    return answer === undefined || answer === "";
  };
  const blocked = question.required && unanswered(question);

  const save = (questionId: string, answer: unknown) => {
    if (!release || !interview.assessmentId || answer === undefined) return;
    const assessmentId = interview.assessmentId;
    const releaseId = release.releaseId;
    setSaving(true);
    setSaved(false);
    queue.current = queue.current
      .then(() => saveSectorAnswer(assessmentId, { releaseId, questionId, answer }))
      .then(
        () => {
          setSaving(false);
          setSaved(true);
        },
        // A failed save is reported, not thrown: the interview must not stop because one request
        // did. The final submit re-sends every answer, so this is recoverable rather than lost.
        (error: unknown) => {
          setSaving(false);
          onError(error instanceof Error ? error.message : String(error));
        },
      );
  };

  /** Typed answers are saved on Next rather than per keystroke — one answer, one write. */
  const advance = () => {
    save(question.questionId, values[question.questionId]);
    setSaved(false);
    setIndex(index + 1);
  };

  const submit = async () => {
    if (!release || !interview.assessmentId) return;
    setSubmitting(true);
    save(question.questionId, values[question.questionId]);
    try {
      // Every answer again, after the queue drains. Each was already saved; re-sending is
      // idempotent and closes the gap left by any save that failed along the way.
      await queue.current;
      await submitSectorAnswers(
        interview.assessmentId,
        release.questions
          .filter((q) => values[q.questionId] !== undefined)
          .map((q) => ({
            releaseId: release.releaseId,
            questionId: q.questionId,
            answer: values[q.questionId],
          })),
      );
      onDone();
    } catch (error) {
      setSubmitting(false);
      onError(error instanceof Error ? error.message : String(error));
    }
  };

  return (
    <Card grain>
      <header className="pb-1">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h2 className="mt-1.5 text-lg font-semibold tracking-tight text-foreground">
          {t("title")}
        </h2>
        {/* Both numbers come from the release, never from a constant: a fifteen-question pack
            says fifteen. */}
        <p className="mt-1 text-sm text-foreground-secondary">
          {t("progress", { current: index + 1, total: questions.length })}
        </p>
      </header>

      <div
        className="mt-3 h-1 overflow-hidden rounded-full bg-surface"
        role="progressbar"
        aria-valuenow={index + 1}
        aria-valuemin={1}
        aria-valuemax={questions.length}
      >
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-300"
          style={{ width: `${((index + 1) / questions.length) * 100}%` }}
        />
      </div>

      <div className="mt-5 rounded-xl border border-hairline bg-surface px-4 py-4">
        {/* Canonical Arabic, always — this is the text a reviewer approved. */}
        <p className="text-base text-foreground" dir="rtl" lang="ar">
          {question.canonicalTextAr}
        </p>
        {question.references.length > 0 && (
          <p className="mt-1.5 text-2xs text-foreground-muted">
            {question.references
              .map((r) => (r.clause ? `${r.framework} · ${r.clause}` : r.framework))
              .join(" · ")}
          </p>
        )}
        <div className="mt-4">
          <SectorAnswerInput
            question={question}
            value={values[question.questionId]}
            onChange={(value, deliberate) => {
              setValues((current) => ({ ...current, [question.questionId]: value }));
              // A click on a choice is a complete answer the instant it happens. A half-typed
              // number is not — that one waits for Next, so the database is never asked to hold
              // "4" on the way to "40".
              if (deliberate) save(question.questionId, value);
            }}
          />
        </div>
        {question.evidenceRequired.length > 0 && (
          <p className="mt-3 text-2xs text-foreground-muted">
            {t("evidence")} {question.evidenceRequired.join(" · ")}
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={submitting || blocked}
          onClick={() => (isLast ? void submit() : advance())}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow hover:opacity-90 disabled:opacity-60"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />}
          {isLast ? t("submit") : t("next")}
          {!isLast && <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={2} aria-hidden />}
        </button>

        {/* Going back shows the answer as it was SAVED. Nothing is re-fetched to do it: every
            answer was written as it was given, so what is on screen and what is in the database are
            the same value. */}
        {index > 0 && (
          <button
            type="button"
            disabled={submitting}
            onClick={() => {
              setSaved(false);
              setIndex(index - 1);
            }}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2 text-sm text-foreground-muted transition-colors duration-150 hover:text-foreground disabled:opacity-60"
          >
            <ArrowLeft className="h-4 w-4 flip-rtl" strokeWidth={2} aria-hidden />
            {t("back")}
          </button>
        )}

        {blocked && <span className="text-2xs text-foreground-muted">{t("required")}</span>}

        {/* Quiet on purpose. It answers "can I close this?" without asking to be watched. */}
        {!blocked && (saving || saved) && (
          <span className="inline-flex items-center gap-1 text-2xs text-foreground-muted">
            {saving ? (
              <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} aria-hidden />
            ) : (
              <Check className="h-3 w-3" strokeWidth={2} aria-hidden />
            )}
            {saving ? t("saving") : t("saved")}
          </span>
        )}
      </div>
    </Card>
  );
}

function SectorAnswerInput({
  question,
  value,
  onChange,
}: {
  question: SectorQuestion;
  value: unknown;
  /** `deliberate` marks an answer that is COMPLETE the moment it changes — a click, not a keystroke.
   *  It is the input's own knowledge; the caller cannot infer it from the value. */
  onChange: (value: unknown, deliberate: boolean) => void;
}) {
  const t = useTranslations("sectorInterview");
  const field =
    "h-9 w-full rounded-lg border border-hairline bg-surface-elevated px-2.5 text-sm text-foreground";

  if (question.type === "boolean") {
    return (
      <div className="flex gap-2" dir="rtl">
        {[true, false].map((option) => (
          <button
            key={String(option)}
            type="button"
            onClick={() => onChange(option, true)}
            className={
              value === option
                ? "h-8 rounded-lg bg-accent px-3.5 text-2xs font-medium text-white"
                : "h-8 rounded-lg border border-hairline px-3.5 text-2xs text-foreground-secondary hover:text-foreground"
            }
          >
            {option ? t("yes") : t("no")}
          </button>
        ))}
      </div>
    );
  }

  if (question.type === "multi_select") {
    // An array, always — including the empty one. "Nothing applies" and "not answered" are
    // different facts, and collapsing them would lose the first.
    const chosen = Array.isArray(value) ? (value as string[]) : [];
    return (
      <ul className="space-y-1.5" dir="rtl">
        {question.options.map((option) => {
          const checked = chosen.includes(option);
          return (
            <li key={option}>
              <label className="flex cursor-pointer items-start gap-2 text-sm text-foreground-secondary">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    onChange(
                      checked ? chosen.filter((o) => o !== option) : [...chosen, option],
                      true,
                    )
                  }
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-accent"
                />
                <span>{option}</span>
              </label>
            </li>
          );
        })}
      </ul>
    );
  }

  if (question.type === "enum") {
    return (
      <select
        dir="rtl"
        className={field}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value, true)}
      >
        <option value="">{t("choose")}</option>
        {question.options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }

  if (question.type === "numeric") {
    return (
      <input
        type="number"
        className={field}
        value={typeof value === "number" ? value : ""}
        onChange={(event) =>
          onChange(event.target.value === "" ? undefined : Number(event.target.value), false)
        }
      />
    );
  }

  if (question.type === "date") {
    return (
      <input
        type="date"
        className={field}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value || undefined, true)}
      />
    );
  }

  return (
    <input
      type="text"
      dir="rtl"
      className={field}
      value={typeof value === "string" ? value : ""}
      onChange={(event) => onChange(event.target.value || undefined, false)}
    />
  );
}
