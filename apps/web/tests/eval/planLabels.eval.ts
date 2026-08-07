/**
 * The label fallback for values that come from PERSISTED plan data (ADR 0066).
 *
 * One stray `"cyber"` in a knowledge pack — every other rule said `"cyber_security"` — was written
 * into a customer's plan and then rendered as `planExecution.pillar.cyber` on their screen. Fixing
 * the pack does not fix the row it already wrote, so reading stored data has to degrade instead of
 * breaking.
 */

import assert from "node:assert/strict";
import { humanizeIdentifier, labelOrIdentifier } from "../../lib/planExecution/labels";

const translate = (key: string): string =>
  key === "pillar.cyber_security"
    ? "Cyber Security"
    : // next-intl returns a MISSING message as the namespace-qualified key, not the key it was
      // given. Getting that wrong is what let the raw key reach a screen in the first place.
      `planExecution.${key}`;

assert.equal(labelOrIdentifier(translate, "pillar", "cyber_security"), "Cyber Security");
assert.equal(labelOrIdentifier(translate, "pillar", "cyber"), "Cyber");
assert.equal(
  labelOrIdentifier(
    () => {
      throw new Error("MISSING_MESSAGE");
    },
    "pillar",
    "cyber",
  ),
  "Cyber",
  "a throwing translator must not take the page down either",
);
assert.equal(humanizeIdentifier("cyber_security"), "Cyber security");
assert.equal(humanizeIdentifier(""), "");

console.log("planLabels.eval: ok");
