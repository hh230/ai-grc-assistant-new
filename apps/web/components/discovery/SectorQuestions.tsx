"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
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
 * All questions are shown at once rather than one at a time: unlike the core interview, this set is
 * fixed the moment it opens — no answer changes which question comes next — so paging through them
 * would add ceremony without adding adaptivity.
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
  const [submitting, setSubmitting] = useState(false);

  const release = interview.release;
  if (!release || !interview.assessmentId) return null;

  const missing = release.questions.filter(
    (q) => q.required && (values[q.questionId] === undefined || values[q.questionId] === ""),
  );

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
        <p className="mt-1 text-sm text-foreground-secondary">
          {t("description", { count: release.questions.length })}
        </p>
      </header>

      <ul className="mt-4 space-y-3">
        {release.questions.map((question) => (
          <li
            key={question.questionId}
            className="rounded-lg border border-hairline bg-surface px-3.5 py-3"
          >
            {/* Canonical Arabic, always — this is the text a reviewer approved. */}
            <p className="text-sm text-foreground" dir="rtl" lang="ar">
              {question.canonicalTextAr}
            </p>
            {question.references.length > 0 && (
              <p className="mt-1 text-2xs text-foreground-muted">
                {question.references
                  .map((r) => (r.clause ? `${r.framework} · ${r.clause}` : r.framework))
                  .join(" · ")}
              </p>
            )}
            <div className="mt-2.5">
              <SectorAnswerInput
                question={question}
                value={values[question.questionId]}
                onChange={(value) =>
                  setValues((current) => ({ ...current, [question.questionId]: value }))
                }
              />
            </div>
            {question.evidenceRequired.length > 0 && (
              <p className="mt-2 text-2xs text-foreground-muted">
                {t("evidence")} {question.evidenceRequired.join(" · ")}
              </p>
            )}
          </li>
        ))}
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={submitting || missing.length > 0}
          onClick={() => void submit()}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow hover:opacity-90 disabled:opacity-60"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />}
          {t("submit")}
        </button>
        {missing.length > 0 && (
          <span className="text-2xs text-foreground-muted">
            {t("remaining", { count: missing.length })}
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
