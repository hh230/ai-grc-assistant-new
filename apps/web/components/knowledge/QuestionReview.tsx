import { useTranslations } from "next-intl";
import { HelpCircle, Paperclip } from "lucide-react";
import type { ReviewQuestion } from "@/lib/knowledge/types";

const IMPORTANCE_TONE: Record<ReviewQuestion["importance"], string> = {
  critical: "bg-danger/10 text-danger",
  high: "bg-warning/10 text-warning",
  medium: "bg-surface-elevated text-foreground-secondary",
  low: "bg-surface-elevated text-foreground-muted",
};

/**
 * One question, as its reviewer needs to judge it — not as a customer will see it.
 *
 * `whyWeAsk` is the reason this component exists: the decision in front of the reviewer is whether
 * the question deserves to be asked at all, and that is unanswerable from the question text alone.
 * It is rendered here and nowhere a customer can reach.
 *
 * A reference with no clause is shown as the framework alone rather than "REGA §—". The model is
 * allowed to say it does not know the clause number, and dressing that absence up as a citation
 * would undo the point of allowing it.
 */
export function QuestionReview({ question }: { question: ReviewQuestion }) {
  const t = useTranslations("knowledgeConsole");

  return (
    <li className="rounded-lg border border-hairline bg-surface px-3.5 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 text-sm text-foreground" dir="rtl" lang="ar">
          {question.canonicalTextAr}
        </p>
        <span
          className={`shrink-0 rounded-md px-1.5 py-0.5 text-2xs font-medium ${IMPORTANCE_TONE[question.importance]}`}
        >
          {t(`importance.${question.importance}`)}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-foreground-muted">
        <span className="font-mono">{question.questionId}</span>
        <span>{t(`questionType.${question.type}`)}</span>
        <span>{question.category}</span>
        {!question.required && <span>{t("question.optional")}</span>}
      </div>

      {question.options.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5" dir="rtl">
          {question.options.map((option) => (
            <li
              key={option}
              className="rounded-md bg-surface-elevated px-1.5 py-0.5 text-2xs text-foreground-secondary"
            >
              {option}
            </li>
          ))}
        </ul>
      )}

      {question.references.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5 text-2xs">
          {question.references.map((reference, index) => (
            <li
              key={`${reference.framework}-${index}`}
              className="rounded-md border border-hairline px-1.5 py-0.5 text-foreground-secondary"
            >
              {reference.clause
                ? `${reference.framework} · ${reference.clause}`
                : reference.framework}
            </li>
          ))}
        </ul>
      )}

      {question.whyWeAsk && (
        <p className="mt-2.5 flex gap-1.5 rounded-lg bg-surface-elevated px-2.5 py-2 text-2xs text-foreground-secondary">
          <HelpCircle className="mt-px h-3 w-3 shrink-0 text-foreground-muted" strokeWidth={1.75} />
          <span>
            <span className="font-medium text-foreground-muted">{t("question.whyWeAsk")} </span>
            {question.whyWeAsk}
          </span>
        </p>
      )}

      {question.evidenceRequired.length > 0 && (
        <p className="mt-1.5 flex items-center gap-1.5 text-2xs text-foreground-muted">
          <Paperclip className="h-3 w-3" strokeWidth={1.75} />
          {question.evidenceRequired.join(" · ")}
        </p>
      )}
    </li>
  );
}
