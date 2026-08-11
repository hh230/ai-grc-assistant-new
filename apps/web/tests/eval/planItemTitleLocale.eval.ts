/**
 * A plan item's title in the reader's language, and what happens when it cannot be.
 *
 * `plan.seed.establish_risk_register.title` is an i18n key — that is what the rule engine emits and
 * why. It used to be resolved to English at draft time and stored as prose, so the one field on a
 * governance plan that could have been bilingual for free arrived monolingual.
 *
 * The stored text stays authoritative and is the fallback, for three cases that all really occur: a
 * plan drafted before the key was kept, a key this deployment has no message for, and a key the
 * engine adds before the translators catch up. A missing translation must never blank a title.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { localisedTitle, planSeedName } from "../../lib/planExecution/localiseTitle";

// --- the key carries the engine's own vocabulary ----------------------------------------------
assert.equal(planSeedName("plan.seed.establish_risk_register.title"), "establish_risk_register");
assert.equal(planSeedName("plan.gap.personal_data_without_policy.rationale"), "personal_data_without_policy");
assert.equal(planSeedName(""), "");
assert.equal(planSeedName("Establish Risk Register"), "");

const has = (known: string[]) => (name: string) => known.includes(name);
const t = (name: string) => `AR:${name}`;

// --- translated when known --------------------------------------------------------------------
assert.equal(
  localisedTitle(
    { title: "Establish Risk Register", titleKey: "plan.seed.establish_risk_register.title" },
    has(["establish_risk_register"]),
    t,
  ),
  "AR:establish_risk_register",
);

// --- a plan drafted before keys were kept must not regress ------------------------------------
assert.equal(
  localisedTitle({ title: "Establish Risk Register", titleKey: "" }, has([]), t),
  "Establish Risk Register",
);

// --- a key with no message falls back rather than rendering the key ---------------------------
// next-intl answers a miss with the namespace-qualified key rather than throwing, so asking
// `has()` first is what stops `planSeed.brand_new_seed` reaching a customer's screen.
assert.equal(
  localisedTitle(
    { title: "Adopt Technical Security Baseline", titleKey: "plan.seed.brand_new_seed.title" },
    has(["establish_risk_register"]),
    t,
  ),
  "Adopt Technical Security Baseline",
);

// --- both locales actually carry every seed the engine can emit -------------------------------
const seeds = new Set<string>();
for (const file of ["core.json", "technology.json", "cloud_provider.json"]) {
  let raw: string;
  try {
    raw = readFileSync(
      `../../v2/packages/governance-discovery/governance_discovery/packs/${file}`,
      "utf-8",
    );
  } catch {
    continue; // a pack this checkout does not ship is not this test's business
  }
  for (const m of raw.matchAll(/"title_key":\s*"plan\.seed\.([^."]+)\.title"/g)) seeds.add(m[1]!);
}
assert.ok(seeds.size > 0, "no plan seeds found — the packs moved and this check went blind");

for (const locale of ["ar", "en"]) {
  const messages = JSON.parse(readFileSync(`messages/${locale}.json`, "utf-8")) as {
    planSeed?: Record<string, string>;
  };
  const missing = [...seeds].filter((s) => !messages.planSeed?.[s]);
  assert.deepEqual(missing, [], `messages/${locale}.json is missing planSeed entries: ${missing}`);
}

// --- the DRAFT report reads the same key, not just the persisted plan -------------------------
// The report path (planGeneration -> ReportItemGroups) dropped `title_key` and rendered the stored
// English straight into an Arabic screen. These three assert the contract the sections now honour:
// the reader's language when the key is known, the other language when it is the reader's, and the
// stored prose — never a raw key — when the engine names a seed this deployment has no message for.
const arMessages = JSON.parse(readFileSync("messages/ar.json", "utf-8")) as {
  planSeed: Record<string, string>;
};
const enMessages = JSON.parse(readFileSync("messages/en.json", "utf-8")) as {
  planSeed: Record<string, string>;
};
const draftItem = {
  title: "Designate Compliance Owner",
  titleKey: "plan.seed.designate_compliance_owner.title",
};
const render = (messages: Record<string, string>) =>
  localisedTitle(draftItem, (name) => name in messages, (name) => messages[name]!);

// ar renders Arabic, and nothing of the stored English survives on screen
const arabic = render(arMessages.planSeed);
assert.equal(arabic, arMessages.planSeed.designate_compliance_owner);
assert.notEqual(arabic, draftItem.title);
assert.ok(!/[A-Za-z]/.test(arabic), `an Arabic screen must not show Latin script: ${arabic}`);

// en stays English
assert.equal(render(enMessages.planSeed), enMessages.planSeed.designate_compliance_owner);

// a seed this deployment has no message for falls back to the stored prose, never the key
assert.equal(render({}), "Designate Compliance Owner");

console.log(`planItemTitleLocale: ok (${seeds.size} seeds, ar + en, draft report path)`);
