/**
 * What a Missions row shows as its subject.
 *
 * The engine's list carries `scope`. For most mission types that is the thing it ran against and
 * belongs on screen; for a governance plan it is the discovery session id — load-bearing for the
 * mission and meaningless to the person reading the row.
 */

import assert from "node:assert/strict";

const OPAQUE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$|^[0-9a-f]{24,}$/i;
const subject = (scope: string): string | null =>
  scope.trim() && !OPAQUE_ID.test(scope.trim()) ? scope.trim() : null;

assert.equal(subject("e5fdb80e-99eb-47cd-89ba-fa04ba7178ae"), null, "a session id is not a subject");
assert.equal(subject("mis_07e33cfa888f48deb6269f25bf31c9d7".slice(4)), null, "nor is a bare hex id");
assert.equal(subject("Technological controls"), "Technological controls");
assert.equal(subject("  ISO 27001 Annex A  "), "ISO 27001 Annex A");
assert.equal(subject(""), null);

console.log("missionSubject.eval: ok");
