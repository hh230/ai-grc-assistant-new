# Deploying a sector

How a new sector — health, education, manufacturing — goes from a written pack to questions a
customer answers. The same five steps every time, in the same order, with nothing to memorise.

The rule this follows: **a human does the deciding, the machine does the ceremony.** Anything that
was only a step because a foreign key needed a row has been removed.

---

## 1. Write the pack

One JSON file in `v2/apps/grc-api/grc_api/knowledge_packs/`, named `<slug>.ar.json`, where the slug
matches an option in the discovery interview's `primary_activity` question — that is how a customer
is matched to a sector.

```
knowledge_packs/
  real_estate.ar.json
  health.ar.json          ← the new one
```

The file declares its own identity, which is why nothing else needs to:

```json
{
  "industry_slug": "health",
  "canonical_name_ar": "الرعاية الصحية",
  "authored_by": "human",
  "questions": [ ... ]
}
```

Each question needs `question_id`, `canonical_text_ar`, `type`, `category`, `importance`,
`why_we_ask`, and at least one entry in `references`. `type` is one of
`boolean · enum · multi_select · numeric · date · text`; `enum` and `multi_select` need two or more
`options`.

Use `multi_select` whenever more than one answer can be true at once. Do **not** offer a single
choice plus an option meaning "more than one" — that records *that* several apply while losing
*which*, and the answer is then something the product cannot act on.

Ship the file with the deployment. There is no upload step and no separate content database: a pack
is code, reviewed in a pull request like anything else.

## 2. Run the migrations

```bash
cd v2/apps/grc-api && uv run python -m grc_api.migrate
```

Idempotent, so it is safe on every deploy. New sectors need no new migration — a pack is data.

## 3. Import it

**Sector Knowledge → Available sector packs → Import.**

One click. It registers the industry from the pack's own `canonical_name_ar` if it is new, and
creates a **draft** release at the next version — v1 on a database that has never seen the sector.

A pack whose file is malformed is listed with its problem instead of an Import button, naming the
question at fault. Fix the file, redeploy, import.

## 4. Review, approve, publish, activate

**Sector Knowledge → the sector → the draft version.**

The review screen shows every question in the canonical Arabic with `why_we_ask` beside it — the
reviewer-only text that never reaches a customer — plus the provenance that makes the release
reproducible.

Then, in order: **Send for review → Approve → Publish → Make this the live version.**

Publishing makes a version *eligible*; activating decides which one customers actually see. They are
separate on purpose, so a version can be ready without being served.

## 5. It reaches customers

Any organization whose `primary_activity` is that sector is asked those questions immediately after
the core interview concludes. Their answers are frozen with the assessment, cite the exact release
version, and shape the wording of the governance plan — never its decisions.

---

## Correcting a pack that is already live

Edit the file, redeploy, **Import again**. That mints a *new version* and leaves the live one
serving customers untouched until somebody activates the new one. A published release is never
edited in place; that is the entire reason it carries a version.

Rolling back is the same screen: activate the older version. No release is demoted, and the
activation history records who changed it and why.

## What still cannot be skipped, and why

**The human gate.** Import creates a draft, never a live release. Authored is not approved. If a
file landing on disk could change what thousands of customers are asked, the pack would be the
decision-maker — and the point of this whole design is that a person is.

**`KNOWLEDGE_APPROVERS`.** Nobody sees this console without being on that list. Unset means nobody,
which is the correct failure for an unconfigured deployment; it never means everybody.
