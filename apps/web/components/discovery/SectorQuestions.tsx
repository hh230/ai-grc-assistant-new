"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { submitSectorAnswers } from "@/lib/sectorInterview/client";
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
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [index, setIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);

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

  async function submit() {
    if (!release || !interview.assessmentId) return;
    setSubmitting(true);
    try {
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
  }

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
            onChange={(value) =>
              setValues((current) => ({ ...current, [question.questionId]: value }))
            }
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
          onClick={() => (isLast ? void submit() : setIndex(index + 1))}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow hover:opacity-90 disabled:opacity-60"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />}
          {isLast ? t("submit") : t("next")}
          {!isLast && <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={2} aria-hidden />}
        </button>

        {/* Going back keeps the answer already given — the whole point of holding them in one map
            rather than posting each as it is answered. */}
        {index > 0 && (
          <button
            type="button"
            disabled={submitting}
            onClick={() => setIndex(index - 1)}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2 text-sm text-foreground-muted transition-colors duration-150 hover:text-foreground disabled:opacity-60"
          >
            <ArrowLeft className="h-4 w-4 flip-rtl" strokeWidth={2} aria-hidden />
            {t("back")}
          </button>
        )}

        {blocked && <span className="text-2xs text-foreground-muted">{t("required")}</span>}
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
  onChange: (value: unknown) => void;
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
            onClick={() => onChange(option)}
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
        onChange={(event) => onChange(event.target.value)}
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
          onChange(event.target.value === "" ? undefined : Number(event.target.value))
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
        onChange={(event) => onChange(event.target.value || undefined)}
      />
    );
  }

  return (
    <input
      type="text"
      dir="rtl"
      className={field}
      value={typeof value === "string" ? value : ""}
      onChange={(event) => onChange(event.target.value || undefined)}
    />
  );
}
