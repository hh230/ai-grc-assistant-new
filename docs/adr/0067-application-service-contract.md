# ADR 0067 — Application Service Contract

> **An Application Service orchestrates; it never decides.**

It opens a transaction when one is needed, calls repository methods, calls domain methods, calls
the LLM, and emits events. It computes nothing and chooses no state transition of its own. An `if`
that turns on **business meaning** belongs in the domain; an `if` that turns on *whether a call
succeeded* is orchestration and belongs here.

Services are named for the **business operation they execute**, never for the objects they know
about. There is no `KnowledgeService`: a name like that answers "what does this know?", and a
class that knows about everything eventually does everything.

## The services

| Service | Calls | Transaction | Emits |
|---|---|---|---|
| `GenerateKnowledgeTemplate` | `ensure_template` → **LLM** → `create_release` | one, inside `create_release` | `KnowledgeTemplateGenerated` |
| `SubmitKnowledgeTemplate` | `submit_for_review` | none — single statement | `KnowledgeTemplateSubmitted` |
| `ApproveKnowledgeTemplate` | `approve_release` | none | `KnowledgeTemplateApproved` |
| `RejectKnowledgeTemplate` | `reject_release` | none | `KnowledgeTemplateRejected` |
| `PublishKnowledgeTemplate` | `mark_released` | none | `KnowledgeTemplatePublished` |
| `ActivateKnowledgeRelease` | `set_active_release` | one, inside the repository | `ActiveReleaseChanged` |
| `RetireIndustry` | `set_active_release(None)` → `set_industry_status` → `retire_release` | one, opened here | `IndustryRetired` |
| `StartAssessment` | `open_assessment` → `record_selection` | one, opened here | `AssessmentStarted` |
| `RecordSectorAnswers` | `save_sector_answers` | one, inside the repository | `SectorAnswersRecorded` |
| `CompleteAssessment` | `complete_assessment` | none | `AssessmentCompleted` |

Ten services. The largest makes **three** calls. A service reaching eight or ten would mean the
use case is really several, and the answer would be to split it — not to let one service grow into
the `KnowledgeService` this design exists to avoid.

## Why some rows say "none"

Five services make a single guarded write. That write is already atomic, and wrapping it in an
explicit transaction would add a boundary that guarantees nothing while implying that something
here is composite. A service exists at those points not for the transaction but because it is
where the **use case** and its **event** live.

`ActivateKnowledgeRelease` and `RecordSectorAnswers` say "inside the repository" for the opposite
reason: those operations are *already* multi-statement and own their transaction (the pointer with
its history; the answer set as a whole). The service must not open a second one around them.

## Where each decision actually lives

Two services look like they decide, and neither does.

**`ActivateKnowledgeRelease`** does not check that the release is releasable. The composite foreign
key does — activating something never released is unrepresentable. The service passes the request
through and lets the database refuse it. Re-checking in Python would be a second, weaker copy of a
rule that is already exact.

**`StartAssessment`** does not choose the template. `primary_activity` *suggests* the active
release, and a human may override it with several; both arrive as arguments. If this service
contained "if no selection was given, use the active one", that default would be a business rule
hidden in the orchestration layer — so the caller resolves it, and this records what was decided
along with what was suggested.

## The primitives `RetireIndustry` composes

`RetireIndustry` is exactly the case that proved this layer exists, and the contract is the
sequence of primitive names — not their count, which changes with time:

    set_active_release(None)
    set_industry_status(...)
    retire_release(...)

The order is not this service inventing a rule. The schema refuses to demote a release while it is
the active one, which **exposed an invariant we had forgotten to model explicitly**: a release must
not be withdrawn underneath customers being interviewed on it. A schema creates no business rules —
it only refuses a state that was already outside the domain. Writing the sequence here is what
modelling that invariant looks like.

Removing `retire_industry` from the repository was right; removing the ability to write the column
was over-correction on my part. `set_industry_status(slug, status)` returns as a **primitive** —
one atomic write, no coordination, which is data access by definition. The distinction is exact:
the repository can *set a status*; only a service can *retire an industry*.

`set_active_release(None)` is **not** a new primitive. It is the other permitted answer to the
question `set_active_release` already asks — see the Repository Contract §2.

## Authorization lives here, not in the route

Every consequential knowledge service takes an `Actor` — the authenticated principal and its roles —
and refuses without `knowledge_approver` before doing anything else. Enforced in the Application
layer, where ADR 0054 puts it, so a new route cannot forget the check by forgetting to write it.

This does not make a service a decision-maker. The *policy* is data (`KNOWLEDGE_APPROVER_ROLE`);
the service only enforces it.

The role is deliberately **not** the tenant-side `approver`. One release serves every customer in a
sector, so the blast radius of a bad one is all of them, and a per-tenant role cannot carry that.

Taking the actor as an `Actor` rather than a string also closes a quieter hole: `created_by`,
`approved_by` and `activated_by` are what an auditor reads a year from now, and a free-string
parameter would let a caller write any name into them.

## Events

Named here, published later. Each service returns its event rather than dispatching it, so wiring
a bus later changes the composition root and no service. Until then the name is still doing work:
it is what the operation means, stated once, where the operation happens.

## The layers are now complete

    Domain              the rules
    Repository          data access
    Application Service coordination
    LLM                 language only

There is no fifth layer, and adding one would need an ADR that argues why these four cannot hold
the responsibility.
