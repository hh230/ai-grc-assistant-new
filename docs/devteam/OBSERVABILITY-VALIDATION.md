# DevTeam Observability — End-to-End Runtime Validation

**Date:** 2026-07-29
**Verdict:** ✅ **13 / 13 checks passed — validated on the real runtime.**
**Gate:** This validation was required before the Dashboard integration. It passed, so the Dashboard
integration may proceed.

---

## 1. What was validated, and what "real" means

The goal was to prove the observability layer works against the **real runtime**, not a mock, before
anything is built on top of it. Two scenarios were run:

| Scenario | Runtime | Mission | What is real | What is canned |
|---|---|---|---|---|
| **A** | `AgentMissionRuntime` | the real quality-review mission (QA → Reviewer) | Foreman-planned plan, real QA + Reviewer agents, the frozen `MissionEngine`, observability, on-disk JSONL journal | nothing (a trivial suite-runner supplies the test results the QA agent reads) |
| **B** | **the real `ContinuousMonitor`** → real `ChainDriver` → real `FixItRuntime` | a real **gated fix-it mission** (Developer → human-approval gate) | the monitor scheduler, the chain policy, the Developer agent, the `MissionEngine`, the approval gate, observability, on-disk JSONL journal | **only the GitHub HTTP layer** — a `CommandRunner` returns a red CI run, exactly as the monitor's own unit tests do |

**Nothing in the observability path is mocked.** In Scenario B the *only* substitution is the external
GitHub API (an I/O boundary), replaced by a canned red-CI response so the run is deterministic and
offline. The monitor lists the (canned) open PR, sees red CI, and drives the real chain, which opens a
real fix-it mission that the real engine executes to the real human-approval gate — all observed.

The daemon now emits observability **by default** — the journal is written unless `--no-journal` is
passed; the opt-in flip has since **landed** (2026-07-31). *(At the time of this 2026-07-29 validation
the flip was still pending; this validation wired observability into the real runtime path the daemon
drives and proved the flip safe to make.)*

---

## 2. Results

Every criterion was checked in **both** scenarios (except "real monitor opened a real mission", which
is Scenario B only). All passed.

| # | Criterion | Scenario A | Scenario B |
|---|---|---|---|
| — | Real monitor opened a real mission | — | ✅ `tick → opened`; mission → `awaiting_approval` |
| 1 | **AgentSessions are created correctly** | ✅ 2 sealed sessions QA→Reviewer; Reviewer verdict `approve` | ✅ 1 Developer session; verdict `proceed`; carries the `diff` artifact |
| 2 | **RuntimeState updates in real time** | ✅ view reported `working` at each agent's `AgentStarted` | ✅ view reported `working` at the Developer's `AgentStarted` |
| 3 | **Journal records are written correctly** | ✅ 12 records, all `schema_version=1`, all carry a typed event | ✅ 7 records, all `schema_version=1`, all carry a typed event |
| 4 | **JournalReader reconstructs the exact RuntimeStateView** | ✅ agents / ownership / sessions / flow **byte-identical** | ✅ byte-identical |
| 5 | **Agent ownership & session tree remain consistent** | ✅ owner `platform:qa`; chain `[qa, reviewer]`; parent/child links bidirectional | ✅ owner `platform:developer`; single root session; no dangling links |
| 6 | **Mission & agent lifecycle stay synchronized** | ✅ mission `COMPLETED`; both agents `IDLE`; no active session; all sessions sealed | ✅ mission `AWAITING_APPROVAL`; Developer step `COMPLETED` & `IDLE` |

### Raw run output

```
Scenario A: quality-review mission (AgentMissionRuntime)
  [PASS] AgentSessions are created correctly            2 sealed sessions QA->Reviewer, reviewer decision=approve
  [PASS] RuntimeState updates in real time              status at AgentStarted: {qa: working, reviewer: working}
  [PASS] Journal records are written correctly          12 records, all schema_version=1, all carry a typed event
  [PASS] JournalReader reconstructs the exact view      agents/ownership/sessions/flow byte-identical
  [PASS] Agent ownership and session tree consistent    owner=qa, chain=[qa, reviewer], links bidirectional=True
  [PASS] Mission & agent lifecycle synchronized         mission=COMPLETED, QA/Reviewer IDLE, all sessions sealed

Scenario B: real ContinuousMonitor -> gated fix-it mission
  [PASS] Real monitor opened a real mission             tick -> opened; mission -> awaiting_approval
  [PASS] AgentSessions are created correctly            1 Developer session, decision=proceed, carries diff artifact
  [PASS] RuntimeState updates in real time              status at AgentStarted: {developer: working}
  [PASS] Journal records are written correctly          7 records, all schema_version=1, all carry a typed event
  [PASS] JournalReader reconstructs the exact view      agents/ownership/sessions/flow byte-identical
  [PASS] Agent ownership and session tree consistent    owner=developer, chain=[developer], links bidirectional=True
  [PASS] Mission & agent lifecycle synchronized         mission=AWAITING_APPROVAL, Developer COMPLETED and IDLE

RESULT: 13/13 checks passed — ALL GREEN
```

A representative journal record (the versioned transport format the reader consumes):

```json
{"schema_version": 1, "event": {"kind": "AgentStarted", "mission_id": "…", "tenant_id": "platform",
 "occurred_at": 1785337341.38, "agent": {"subsystem": "platform", "role": "qa", "key": "platform:qa"},
 "step_id": "s1", "phase": "working"}}
```

---

## 3. How each criterion was proven (method, not just outcome)

- **Sessions created correctly** — asserted the sealed `AgentSession` records directly off the live
  registry: correct agent/step/mission, `duration_ms` measured, `status = COMPLETED`, and the
  decision/artifacts captured (Reviewer's `approve`, the Developer's `proceed` + `diff`).
- **Real-time updates** — a probe wired as a downstream **after** the registry snapshots each agent's
  status at the instant its `AgentStarted` is observed. It saw `WORKING` every time, proving the view
  reflects the change immediately, not only at the end of the run.
- **Journal written correctly** — parsed the on-disk file: every line is valid JSON, every record
  carries `schema_version = 1` and a typed `event`.
- **Exact reconstruction** — rebuilt the view in a **separate reader** (`devteam_view_from_journal`,
  which is the only thing the Dashboard will call) and asserted its `agents()`, `ownership()`,
  `mission_sessions()`, and `mission_flow()` are **equal** to the live view's. Replay is deterministic
  (same facts, same order → identical session ids and tree), so equality is exact.
- **Ownership & tree consistency** — verified the owner is the first agent, and that every child
  session's `parent_session_id` points to a real parent that lists it back in `child_session_ids`
  (bidirectional), in both the live and reconstructed views.
- **Lifecycle synchronization** — checked that mission state and agent state agree at the terminal:
  on `COMPLETED`, no agent is left `WORKING` and no session is left active; at the human gate,
  `AWAITING_APPROVAL` coincides with the Developer having `COMPLETED` its step.

---

## 4. Findings worth recording

- **The human gate is a *human* wait, not an agent wait (correct).** In the fix-it plan the approval
  gate sits on `apply_patch` — a **non-agent** Git step that runs *after* the Developer's step. So when
  the mission is `AWAITING_APPROVAL`, the Developer has already `COMPLETED` its session and is `IDLE`;
  the pending party is the human approver, not an agent. No agent is ever stuck `WORKING` while the
  mission is paused. (The `WAITING` agent status exists for a gate that pauses *mid-agent-step*, which
  the current DevTeam plans never produce, since gates are placed on Git steps — it is available for
  other agent systems.)
- **Reconstruction is byte-exact because seeding matches.** The reader seeds its roster with the *same*
  `seed_roster` (display names included) the live runtime uses, and replays deterministic session ids —
  so the reconstructed `RuntimeStateView` equals the live one field-for-field. (A validation-driven fix:
  the reader now takes a seeding callback instead of a bare id list, so it seeds identically.)
- **Journal carries facts only; derivations are recomputed.** `AgentStatusChanged` (a derived event) is
  not journaled; the reader re-derives it on replay. This keeps the journal minimal and the
  reconstruction faithful.

---

## 5. Reproducing this validation

Permanent regression guard (runs in CI via the standalone-package sweep):

```bash
uv run --directory devteam/packages/devteam-runtime pytest tests/test_observability_validation_e2e.py
```

The three tests there encode the same scenarios and assertions used for this report.

---

## 6. Conclusion

The observability layer is correct and consistent against the real runtime — real missions, real
agents, real engine, real monitor path, real on-disk journal — across session creation, real-time
state, journal transport, exact reconstruction, the ownership/session tree, and lifecycle
synchronization. **The validation gate is satisfied; the Dashboard integration may proceed.**
