# Why V1 Looks the Way It Does

> **What this document is.** A short story — not an ADR, not an architecture spec, not a
> checklist. It explains *why* the V1 product has the shape it has: why some obvious-looking
> things were deliberately **not** built, and what each of those refusals protects. Read it
> before you propose changing the shape of V1, because most "obvious" changes here have already
> been considered and declined for a reason.
>
> **What this document is not.** It is not the source of truth for *how* anything works — the
> nine Foundation docs and the ADRs are. This is the source of truth for *why it feels this way*.
> If this story and the code ever disagree, one of them is a bug; find out which.
>
> **Audience.** Any engineer, designer, or product person joining after V1. If you find yourself
> in a meeting re-opening one of the questions below, this document exists so that discussion
> starts from the answer we already paid for, not from zero.

---

## The one idea underneath all of it

Everything below is a consequence of a single discipline:

> **Product language is not implementation language.**

The user speaks in GRC: *missions, evidence, results, decisions, coverage*. The system speaks in
mechanism: *plans, tools, pipelines, chunks, projections, aggregates, ORM rows, step ids*. V1's
whole job is to keep these two vocabularies from bleeding into each other. Every time an
implementation word leaked toward the surface — *Deliverable, Approval, Document, Draft, run* —
we pushed it back down and put a product word on top.

This is not decoration. In a regulated domain, the words are the mental model, and the mental
model is what an auditor, a practitioner, and a new engineer each carry in their head. When the
words are honest, the product is trustworthy and the system stays small. When they blur, the
product starts to *look* like the machine — and a machine is exactly what a GRC practitioner
does not want to operate.

The six stories below are all the same story told six times.

---

## 1. Why there is no Draft

The most tempting thing to build on the New Mission screen was a **Draft** — a half-made mission
you save, come back to, edit, and only later turn into a real one. Every tool has drafts. It
feels like table stakes.

We almost added a `MissionDraft` aggregate: its own identity, its own lifecycle, its own storage,
its own state transitions. That is a whole new domain concept — and it would have been wrong.

The moment we stopped was the Reality Gate on S7. Before writing a line of code, we asked the
Core a plain question: *how does a mission actually get created?* The answer, read straight from
the lifecycle, was that `create()` returns a **real Mission immediately** (status `CREATED`), and
the lifecycle has **no `DRAFT` state at all** — it goes `created → planned → executing →
awaiting_approval → resumed → completed / failed / cancelled / archived`.

So "Draft" was never a domain truth. It was a **feeling** the user has while filling in a form —
"this isn't started yet." That feeling is real, but it is **Presentation State**: it lives in the
browser, in the New Mission form, for a few seconds. It does not need an aggregate, a table, a
lifecycle, or a single line of backend code.

**What it protects.** One phantom concept, unbuilt, is one entire slice of complexity that will
never need migrations, never need approval rules, never need a "draft expired" cron job, never
confuse an auditor asking "what is a draft mission, legally?" The Reality Gate's best result to
date was not catching a bug — it was **disproving an assumption before it became code**. That is
cheaper than any bug, because a bug you can see; an unnecessary concept you carry forever.

> If someone later says "users want to save unfinished missions," the answer is not a Draft
> aggregate. It is: persist the *form's* values (Presentation State), or — if they truly want a
> parked, resumable unit of work — that is a real Mission in `CREATED`, which already exists.
> Reach for a new concept only when an existing one genuinely cannot carry the need.

---

## 2. Why it is a "Result", not a "Deliverable"

Inside the system, a completed mission produces a `Deliverable`: a domain object with sections,
citations, coverage, exportable to Markdown/DOCX/PDF. That word is correct — in the domain.

On screen, the user never sees the word "Deliverable." They see **Result**.

The reason is what the user is actually asking at that screen. They are not asking "show me the
document you generated." They are asking one thing: **"Can I rely on this?"** A *Deliverable*
sounds like a file to download. A *Result* sounds like the outcome of work you can trust or
question. So the page is ordered as an argument for trust, not as a document: the **Trust Bar**
first (evidence count · human review · last updated), then the summary, then coverage, then the
evidence, then the gaps, and **export last** — because exporting is the final action, not the
first.

We also refused, more than once, to add a field to the Result *just because the UI wanted it*
(for example, a top-level `framework` on the Trust Bar). Framework appears only where it is
**naturally derivable** — inside the coverage of a Gap Assessment, where the domain already knows
it. A field added to please a screen is a lie the backend has to keep telling.

**What it protects.** The Result stays a *derived* thing — a view of the mission, generated on
demand, never a stored, editable, separately-versioned artifact. That single decision closes a
dozen questions that would otherwise never end: can you edit a deliverable? version it? approve
the deliverable separately from the mission? does it survive if the mission is deleted? Because
Result is *derived from Mission*, all of those answers are "the question doesn't apply." Approval
is on the **mission**, not the document. Trust comes from the **evidence**, not the prose.

---

## 3. Why the Dashboard is a Projection, not a God Endpoint

The Dashboard has to answer **"What needs my attention right now?"** — waiting decisions, running
missions, failures, recent work, a coverage snapshot. The lazy way to build that is one big
endpoint that reaches into everything and returns a bag of numbers: the God Endpoint.

We built it instead as a **Dashboard Projection** that is **computed on read** — it *composes
existing read models* at query time and stores nothing of its own. There is no dashboard table,
no dashboard projector, no new write path. The attention counts come from the mission read model;
the coverage snapshot comes from the same coverage the Result already derives. Two independent
providers behind one projection, each reusable on its own (the coverage rollup will serve future
executive and vendor dashboards without being a limb of *this* screen).

We also drew a hard line around the word "attention." The Dashboard is **not analytics**. It
deliberately does *not* show document counts, storage used, last upload time, user counts — all
the vanity metrics a dashboard accumulates. Every card has to earn its place by serving the one
question. If a number doesn't help you decide *what to do next*, it belongs on an analytics page
that V1 does not have.

**What it protects.** No new storage means no new thing to keep consistent, no projector to run,
no migration. "Compute on read until performance actually demands materialization" keeps the
default at *no machinery*. And keeping the Dashboard to one question stops it from slowly becoming
the ERP home screen — the place where every team eventually demands their favorite tile.

---

## 4. Why "Evidence Collections", not "Documents"

Under the hood, uploaded files become `Document` projections with ingestion status, chunks,
embeddings, pgvector rows. On the Knowledge screen, the user does not see a file manager. They see
**Evidence Collections** grouped by GRC kind: Policies, Procedures, Standards, SOC Reports, Risk
Registers.

The unit on that screen is the **collection**, not the file. A practitioner does not think "I have
14 PDFs." They think "I have my policies, my SOC reports, my risk registers" — and they drill into
a collection to see what is inside. The file is real, but it is *implementation* of evidence, not
the thing itself.

Two small refusals made this honest. First, **upload is an event, not a document**: uploading
triggers ingestion, which *projects* a Document, which *joins* a collection — we never conflated
"the user dropped a file" with "a Document exists." Second, the label for anything the system
can't classify is **Unclassified**, shown last — not "Other (1)". "Other" is a junk drawer;
"Unclassified" is an honest, temporary state that invites fixing. And grouping is **presentation**:
there is no `GET /collections` endpoint, because a collection is how the client *renders*
documents, not a thing the server stores.

**What it protects.** The user's mental model of their own evidence stays intact — organized the
way a GRC professional organizes evidence, not the way a filesystem organizes bytes. Chunks,
embeddings, and pgvector never surface, because the user is never asked to think about retrieval
mechanics to answer "what evidence do we have?"

---

## 5. Why "Decisions", not "Approvals"

Internally this is an approval queue: missions paused at a human gate, each with an
`ApprovalRequest`. The screen is called **Decisions**, and it asks **"What decisions are waiting
for me?"**

The difference is not cosmetic. An *Approvals* screen invites you to build a list of *missions*
that happen to need approval — mission rows with an approve button bolted on. But the unit the
reviewer cares about is the **decision**: *what am I being asked to allow, and can I decide it in
five seconds?* So each card leads with the **proposed action**, uses the mission only as context,
shows the evidence behind it with a "Review evidence →" link, and orders the queue by **age,
oldest first** — because the thing that has waited longest is the thing most likely to be blocking
someone.

This was also the slice where we changed the *least*. The approve/reject command and the decision
semantics already existed from Mission Detail (S2); the endpoint already existed. The entire
Decisions experience was **composed from what was already there** — the only genuinely new piece
was a read-side projection to gather the waiting decisions (and recent ones, so the screen stays
alive when nothing is waiting). A whole product surface, almost entirely reused.

**What it protects.** The reviewer's job stays a *decision* job, not a *list-management* job. And
the fact that Decisions needed no new command or contract is itself the proof of a healthy system:
when the language is right, a new screen is mostly *arrangement*, not *construction*.

---

## 6. Why Product Expansion adds questions before it adds behavior

Look at the order the seven slices were built and a pattern appears. The first four (Missions,
Mission Detail, Result, Knowledge) built the system's **language**. The next two (Dashboard,
Decisions) added new **questions** — each is a new *read*, a new way to look at state that already
existed, with no new command, no new aggregate, no new domain concept. Only the **last** slice,
New Mission, added new **behavior** — the first write, the first thing that *creates* work.

That order was not an accident; it became a thesis: **Product Expansion adds questions before it
adds behavior.** New reads are cheap and safe — they cannot corrupt state, they compose from
projections, they are almost pure arrangement. New writes are where real risk lives — new
commands, new transitions, new ways to be wrong. So we spent the questions first, proved the
language could answer them, and only then spent the one behavior V1 needed.

You can see it in the reuse numbers. The read slices reused ~72–73% of what existed. New Mission —
the write slice — reused ~61%, **deliberately the lowest**, and that low number is the *correct*
signal, not a failure: it says "this is the slice that actually added something new." A reuse
ratio is not a score to maximize. 92% reuse with zero new components can mean a rigid system
resisting a change it *should* accept. The number is a **conversation starter**: every new
component must be *justified* as a genuinely new concept — never rejected merely for being new.

**What it protects.** The system grows in the safe direction first. By the time you add behavior,
the language has already been stress-tested by the questions it had to answer. Behavior lands on
proven ground.

---

## The method behind the stories

None of these six decisions came from taste or luck. They came from four guards that were built
into the process precisely so that the *next* engineer doesn't have to be as careful — the guard
is careful for them:

- **The Reality Gate.** Before the first commit of a slice, investigate what the system *actually*
  provides — name the Source of Truth, and ask: *can this slice be composed from what already
  exists?* This is the guard that killed the Draft (Story 1), refused the God Endpoint (Story 3),
  and made Decisions mostly reuse (Story 5). Its highest purpose is to disprove a wrong assumption
  *before* it becomes code.
- **The Freeze.** A frozen doc or contract changes **only** when implementation reveals a genuine
  contradiction — measured by evidence, never by "it would be easier." When code and a frozen doc
  disagree, the default assumption is that the *code* is the bug. This is what kept the product
  language honest instead of drifting toward whatever the machine found convenient.
- **The Reuse Ratio.** A number reported every slice — not to maximize, but to *notice*. High
  reuse on a read slice is health; low reuse on a write slice is honesty; high reuse where you
  *should* have grown is rigidity worth questioning.
- **New Component Justification.** Every new component earns one line explaining why it is a new
  *concept* and not a duplicate. "New is bad" is not the rule. "New must be justified" is.

The stories are what these guards produced. The guards are why the stories will keep being true
after the people who wrote them have moved on.

---

## How to use this document

When a future change tempts you to undo one of these six — to add a Draft, to expose the
Deliverable as an editable file, to hang one more tile on the Dashboard, to turn Knowledge into a
file manager, to make Decisions a mission list, to rush a new write before its question is
answered — **come here first.** Re-read the story. If the change still makes sense *knowing what
the refusal was protecting*, then make it deliberately, and add a new story explaining why the old
one no longer holds. That is a healthy evolution.

What is not healthy is re-litigating the question from zero, as if the reasoning were never paid
for. It was paid for. This document is the receipt.

---

*A living story. When V1's shape genuinely changes, change the story with it — never let the
product and its own explanation drift apart.*
