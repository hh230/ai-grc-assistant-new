/**
 * Labels for values that arrive from PERSISTED data rather than from this codebase.
 *
 * A plan item's `pillar` was written into the database when the plan was generated, possibly months
 * and several releases ago. Looking that value up as a translation key means a value the interface
 * has no label for throws — which is how one stray `"cyber"` in a knowledge pack (every other rule
 * said `"cyber_security"`) turned a customer's whole plan page into an error.
 *
 * Fixing the pack was right, and not enough: the row it already wrote still says `"cyber"`. Stored
 * data outlives the vocabulary that produced it, so reading it must degrade rather than break —
 * an unlabelled pillar shows as readable text, and the plan still renders.
 */

/** Turns an unlabelled identifier into something a person can read: `cyber_security` → `Cyber security`. */
export function humanizeIdentifier(value: string): string {
  const words = value.replace(/[_-]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : value;
}

/**
 * `t(key)` when the interface has a label, the humanized identifier when it does not.
 *
 * `next-intl` reports a missing message by throwing in development and returning the key in
 * production — two different failures for one cause. This makes it one, and a visible one: a
 * reviewer sees `Cyber` where every sibling reads `Cyber Security`, which is a legible symptom
 * rather than a blank page.
 */
export function labelOrIdentifier(
  translate: (key: string) => string,
  namespace: string,
  value: string,
): string {
  const key = `${namespace}.${value}`;
  try {
    const label = translate(key);
    // A missing message comes back as the key itself — and next-intl returns it NAMESPACE-QUALIFIED
    // (`planExecution.pillar.cyber`), not as the key that was passed in. Comparing against the
    // argument therefore never matches, which is exactly the bug that let the raw key reach a
    // customer's screen once already.
    return label.endsWith(key) ? humanizeIdentifier(value) : label;
  } catch {
    return humanizeIdentifier(value);
  }
}
