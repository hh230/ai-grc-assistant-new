/**
 * A plan item's title in the reader's language.
 *
 * `plan.seed.establish_risk_register.title` is an i18n key — that is what the rule engine emits and
 * why. It used to be resolved to English at draft time and stored as prose, so the one field on a
 * governance plan that could be bilingual for free arrived monolingual.
 *
 * The stored text remains authoritative and is the fallback, in three cases that all really happen:
 * a plan drafted before the key was kept, a key this deployment has no message for, and a key the
 * engine adds before the translators catch up. A missing translation must never blank a title.
 */

/** `plan.seed.establish_risk_register.title` → `establish_risk_register`. */
export function planSeedName(key: string): string {
  const match = /^plan\.(?:seed|gap)\.(.+)\.(?:title|objective|rationale)$/.exec(key);
  return match?.[1] ?? "";
}

/**
 * @param has  `next-intl`'s `has()` for the `planSeed` namespace — asked BEFORE translating,
 *             because next-intl returns the namespace-qualified key string on a miss rather than
 *             throwing, and rendering `planSeed.foo` to a customer is worse than English.
 */
export function localisedTitle(
  item: { title: string; titleKey: string },
  has: (name: string) => boolean,
  t: (name: string) => string,
): string {
  const name = planSeedName(item.titleKey);
  return name && has(name) ? t(name) : item.title;
}
