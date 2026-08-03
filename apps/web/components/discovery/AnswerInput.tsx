"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { optionsNamespaceFor } from "@/lib/discovery/optionLabels";
import type { DiscoveryQuestion } from "@/lib/discovery/types";

interface AnswerInputProps {
  question: DiscoveryQuestion;
  initialValue?: unknown;
  disabled?: boolean;
  onSubmit: (value: unknown) => void;
  onSkip?: () => void;
}

const buttonBase =
  "inline-flex h-9 items-center justify-center gap-1.5 rounded-lg px-3.5 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50";
const primaryButton = cn(
  buttonBase,
  "bg-accent text-white shadow-glow hover:opacity-90 active:scale-[0.98]",
);
const secondaryButton = cn(
  buttonBase,
  "border border-hairline-strong bg-surface text-foreground-secondary hover:bg-surface-2",
);
const choiceButton = (selected: boolean) =>
  cn(
    "inline-flex h-10 items-center justify-center gap-1.5 rounded-lg border px-4 text-sm font-medium transition-colors duration-150",
    selected
      ? "border-accent bg-accent/10 text-accent-foreground"
      : "border-hairline-strong bg-surface text-foreground-secondary hover:bg-surface-2",
  );

export function AnswerInput({ question, initialValue, disabled, onSubmit, onSkip }: AnswerInputProps) {
  const t = useTranslations();
  const optionsNs = optionsNamespaceFor(question.id);
  const [textValue, setTextValue] = useState("");
  const [numberValue, setNumberValue] = useState("");
  const [dateValue, setDateValue] = useState("");
  const [selectValue, setSelectValue] = useState("");
  const [multiValue, setMultiValue] = useState<string[]>([]);

  useEffect(() => {
    setTextValue(typeof initialValue === "string" ? initialValue : "");
    setNumberValue(typeof initialValue === "number" ? String(initialValue) : "");
    setDateValue(question.valueType === "date" && typeof initialValue === "string" ? initialValue : "");
    setSelectValue(
      question.valueType === "enum" && !question.allowMultiple && typeof initialValue === "string"
        ? initialValue
        : "",
    );
    setMultiValue(question.allowMultiple && Array.isArray(initialValue) ? (initialValue as string[]) : []);
  }, [question.id, question.valueType, question.allowMultiple, initialValue]);

  const optionLabel = (option: string) => t(`${optionsNs}.${option}` as never);

  // --- boolean: two buttons, submit immediately (a quick, conversational yes/no) -------------
  if (question.valueType === "boolean") {
    return (
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={() => onSubmit(true)}
          className={choiceButton(initialValue === true)}
        >
          {t("discoveryInterview.answer.yes")}
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onSubmit(false)}
          className={choiceButton(initialValue === false)}
        >
          {t("discoveryInterview.answer.no")}
        </button>
      </div>
    );
  }

  // --- enum, single-select, rendered as buttons (incl. tri-state "yes/partially/no") ---------
  if (question.valueType === "enum" && !question.allowMultiple && question.uiHint === "buttons") {
    return (
      <div className="flex flex-wrap gap-2">
        {(question.options ?? []).map((option) => (
          <button
            key={option}
            type="button"
            disabled={disabled}
            onClick={() => onSubmit(option)}
            className={choiceButton(initialValue === option)}
          >
            {optionLabel(option)}
          </button>
        ))}
      </div>
    );
  }

  // --- enum, single-select, dropdown -----------------------------------------------------
  if (question.valueType === "enum" && !question.allowMultiple) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={selectValue}
          disabled={disabled}
          onChange={(event) => setSelectValue(event.target.value)}
          className="h-10 min-w-[220px] rounded-lg border border-hairline-strong bg-surface px-3 text-sm text-foreground focus:border-accent focus:outline-none"
        >
          <option value="" disabled>
            {t("discoveryInterview.answer.selectPlaceholder")}
          </option>
          {(question.options ?? []).map((option) => (
            <option key={option} value={option}>
              {optionLabel(option)}
            </option>
          ))}
        </select>
        <NextButton disabled={disabled || !selectValue} onClick={() => onSubmit(selectValue)} t={t} />
      </div>
    );
  }

  // --- enum, multi-select, chips ----------------------------------------------------------
  if (question.valueType === "enum" && question.allowMultiple) {
    const toggle = (option: string) =>
      setMultiValue((current) =>
        current.includes(option) ? current.filter((v) => v !== option) : [...current, option],
      );
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {(question.options ?? []).map((option) => {
            const selected = multiValue.includes(option);
            return (
              <button
                key={option}
                type="button"
                disabled={disabled}
                onClick={() => toggle(option)}
                className={choiceButton(selected)}
              >
                {selected && <Check className="h-3.5 w-3.5" strokeWidth={2.5} />}
                {optionLabel(option)}
              </button>
            );
          })}
        </div>
        <div className="flex gap-2">
          <NextButton
            disabled={disabled || multiValue.length === 0}
            onClick={() => onSubmit(multiValue)}
            t={t}
          />
          {!question.required && onSkip ? <SkipButton disabled={disabled} onClick={onSkip} t={t} /> : null}
        </div>
      </div>
    );
  }

  // --- numeric ---------------------------------------------------------------------------
  if (question.valueType === "numeric" || question.valueType === "percentage") {
    const parsed = Number(numberValue);
    const isValid = numberValue.trim() !== "" && Number.isFinite(parsed);
    return (
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="number"
          inputMode="numeric"
          value={numberValue}
          disabled={disabled}
          onChange={(event) => setNumberValue(event.target.value)}
          placeholder={t("discoveryInterview.answer.numberPlaceholder")}
          className="h-10 w-40 rounded-lg border border-hairline-strong bg-surface px-3 text-sm text-foreground focus:border-accent focus:outline-none"
        />
        <NextButton disabled={disabled || !isValid} onClick={() => onSubmit(parsed)} t={t} />
      </div>
    );
  }

  // --- date --------------------------------------------------------------------------------
  if (question.valueType === "date") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="date"
          value={dateValue}
          disabled={disabled}
          onChange={(event) => setDateValue(event.target.value)}
          className="h-10 rounded-lg border border-hairline-strong bg-surface px-3 text-sm text-foreground focus:border-accent focus:outline-none"
        />
        <NextButton disabled={disabled || !dateValue} onClick={() => onSubmit(dateValue)} t={t} />
        {!question.required && onSkip ? <SkipButton disabled={disabled} onClick={onSkip} t={t} /> : null}
      </div>
    );
  }

  // --- free text (short clarification) ----------------------------------------------------
  return (
    <div className="space-y-2">
      <textarea
        value={textValue}
        disabled={disabled}
        onChange={(event) => setTextValue(event.target.value)}
        placeholder={t("discoveryInterview.answer.textPlaceholder")}
        rows={2}
        className="w-full resize-none rounded-lg border border-hairline-strong bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
      />
      <div className="flex gap-2">
        <NextButton
          disabled={disabled || textValue.trim() === ""}
          onClick={() => onSubmit(textValue.trim())}
          t={t}
        />
        {!question.required && onSkip ? <SkipButton disabled={disabled} onClick={onSkip} t={t} /> : null}
      </div>
    </div>
  );
}

function NextButton({
  disabled,
  onClick,
  t,
}: {
  disabled?: boolean;
  onClick: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className={primaryButton}>
      {t("discoveryInterview.next")}
      <ChevronRight className="h-4 w-4 rtl:rotate-180" strokeWidth={2} />
    </button>
  );
}

function SkipButton({
  disabled,
  onClick,
  t,
}: {
  disabled?: boolean;
  onClick: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className={secondaryButton}>
      {t("discoveryInterview.skip")}
    </button>
  );
}
