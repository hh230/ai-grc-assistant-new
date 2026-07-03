/**
 * Script-detection helpers for verifying generated content actually landed in the
 * requested language — LLMs asked for a non-English JSON payload sometimes drift back to
 * English for individual string fields despite explicit instructions (a known reliability
 * gap, most common with `response_format: json_object`). Used to gate a regeneration retry
 * in `lib/analysis/service.ts` and to assert against in the Arabic-generation regression
 * check. Isomorphic (no Node-only APIs).
 */

const ARABIC_SCRIPT_PATTERN = /[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]/;

export function containsArabic(text: string | undefined | null): boolean {
  return Boolean(text && ARABIC_SCRIPT_PATTERN.test(text));
}

/** True if none of the given strings (ignoring empty/undefined ones) contain Arabic script. */
export function missingArabic(texts: Array<string | undefined | null>): boolean {
  const nonEmpty = texts.filter((t): t is string => Boolean(t && t.trim().length > 0));
  if (nonEmpty.length === 0) return false;
  return !nonEmpty.some(containsArabic);
}
