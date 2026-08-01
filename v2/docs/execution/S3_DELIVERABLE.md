# Slice S3 — Result (the mission's Deliverable)

> The end of Time-to-Deliverable: the sellable, auditable artifact a mission produces. Derived from
> the **Deliverable** View ([../WIREFRAMES_V1.md](../WIREFRAMES_V1.md)), **Screen Flow 3**
> ([../SCREEN_FLOWS_V1.md](../SCREEN_FLOWS_V1.md)), and the Deliverable/Export endpoints
> ([../REST_API_CONTRACT_V1.md](../REST_API_CONTRACT_V1.md) §4, §7). Built on the existing
> `deliverables` package (Gap Matrix / *Evidence Mapping* + MD/DOCX/PDF export) — **derived from the
> completed mission, never stored** (ADR 0053; Domain Model). **Status:** ✅ **CLOSED** (owner sign-off
> 2026-07-22 — Approved with changes, applied & verified). **Last updated:** 2026-07-22.

---

## Design rules (owner review — locked before the contract)

1. **A Deliverable is a *derived decision artifact*, not a report.** The user does not come to read a
   document; they come to answer *"can I rely on this result?"* So **page order matters more than
   content** — the page is built as a decision surface, not a Markdown dump with an Export button.
2. **The page order is fixed:** **Trust Bar → Executive Summary → Coverage → Evidence → Exceptions /
   Gaps → Export.** Not "Markdown report, then Export PDF."
3. **In the UI the page is called "Result"** (or "Assessment Result"); **"Deliverable" stays in the
   domain and the API only** — product language ≠ implementation language (the same reason
   `MissionProjection` / `ProjectionPort` are invisible to the user).
4. **Export is the *last* action on the page, not the first** — the decision comes before the download.
5. **Result is evidence-first, not prose-first.** The page opens with what makes the user *trust* the
   result (the Trust Bar, coverage, evidence), not with the prose the AI wrote. This one line is the
   whole philosophy of S3 — consistent with transparency, the Trust Bar, citations, and "AI explains
   before it recommends."
6. **Result adapts to the mission, not the mission to the Result.** The page shape follows the mission
   *type* (a Gap Assessment shows Coverage/Framework/Gaps; a Policy Review does not) — the UI adapts to
   the mission, never the reverse. (Mission-first · derived deliverable · the product drives the code.)
7. **Confidence belongs to the Sections, not the Trust Bar.** Since the Core carries a per-section
   confidence, it is shown *inside each section* ("Executive Summary — Confidence: High"), where the
   user reads the content it qualifies. The Trust Bar stays universal: `#evidence · human-review ·
   updated`.
8. **`ResultView` is stable; `ResultContent` is polymorphic.** The Trust Bar + header/metadata are the
   same for every result; the *content* changes per family (`GapAssessmentContent`, and later
   `VendorAssessmentContent`, `PolicyReviewContent`). A new result type is a new `ResultContent`, never
   a new field on `ResultView` — so it cannot decay into a God DTO. (The type-level form of "Result
   adapts to the mission.")
9. **Builder selection takes the whole mission** (`registry.for_mission(mission, mission_type)`), not
   just its type — so selection can grow to framework / capability / version / tenant flags without
   changing the contract or any caller.
10. **The Builder builds `ResultContent` only; `ResultQuery` builds the `ResultView`.** The Trust Bar,
    title, and metadata are the *frame*, not the content — assembled once by the query, so no builder
    re-derives them and none can drift into a "disguised Presenter." One job per layer: **Builder =
    content · Query = page · Presenter = display.**

11. **A builder depends on a `FrameworkProvider` contract, not `FrameworkLibrary.from_bundled()`.** The
    framework source (bundled files today; a DB, a service, or a per-tenant catalog tomorrow) sits
    behind a port — the same inversion as `MissionAccess` / `ProjectionPort` / `MissionWorkflow`; the
    builder never changes.
12. **Export goes through an `ExportService` (a contract), not `if fmt == "pdf"` in the route.** The
    service holds one `Exporter` per format (md/docx/pdf), routed like the builder registry. Concrete
    exporters (wrapping the `deliverables` render/export functions) are wired in the composition root.
13. **A builder depends on a `DeliverableProvider` contract, not `build_deliverable()` directly** — so
    caching/telemetry/flags/versioning slot in behind the port. **The Gap builder *enriches* this base
    Deliverable (adds the gap matrix); it does not rebuild the sections.** And **`ExportService`
    exports the `ResultView`** (what the user sees), not the Mission — so export is independent of how
    the result was built. *With this, every external dependency of the Application layer is a contract:
    `MissionAccess · MissionWorkflow · ProjectionPort · FrameworkProvider · DeliverableProvider ·
    Exporter/ExportService` — no direct call into an implementation package anywhere in the layer.*
14. **The frontend uses a `ResultPresenterRegistry`, not `switch(content.kind)` in the page** — the
    front-end counterpart of the `DeliverableBuilderRegistry`. Each presenter decides how its content
    renders **and which export formats it offers** (`availableExports`). A new result type is a new
    presenter (an addition), never a `ResultPage` edit. (This is Presentation language, not Application
    — outside the Application Contract Freeze.)

*Future architectural notes (recorded, not implemented — do not delay S3):*
- *`TrustBar` is becoming a **product primitive** (Mission Detail · Result · Vendor Review · Policy
  Review). When the second consumer lands, move it out of `result_views.py` into a shared presentation
  module.*
- *A `ResultPresenter` today does `render` + `availableExports`. As result types accrue (S4/S5) it may
  gain section order, show/hide, headings, badges, status colours, icons — drifting toward a ViewModel
  builder / God Object. If that happens, split it internally: `layout()` · `sections()` · `exports()`
  · `render()`. Note only; act when the responsibility actually grows.*

*(Cross-cutting, now a Design Review Checklist rule: every view that ends in a user decision opens with
a Trust Bar — Result qualifies.)*

---

## Core Capability Gate — answered **before any commit** (no assumptions)

*S1 (type/scope) and S2 (retry) both broke because the UI assumed more than the Core provided. So before
building, the question is: **what can the Core produce today as a Result, with no assumption?** Verified
against the `deliverables` package (`build_deliverable`, `build_gap_matrix`):*

| Result element | In the Core today? | Derived? | Notes |
|---|---|---|---|
| Executive Summary / Sections | ✅ | yes | `Deliverable.sections` — heading + body from step outputs; **any** mission |
| Evidence citations | ✅ | yes | `Section.citations` (= `StepResult.source_ids`) |
| Confidence | ✅ | yes | `Section.confidence` — per section (**not deferred**) |
| Coverage % | ✅ *(Gap Assessment only)* | yes | `GapMatrix.coverage` (deterministic) |
| Framework | ✅ *(Gap Assessment only)* | yes | `GapMatrix.framework` — a **natural** part of the matrix, not a field added for the UI |
| Exceptions / Gaps | ✅ *(Gap Assessment only)* | yes | `GapMatrix.gaps` |
| Human review | ✅ | yes | from the mission's approval |
| #evidence sources · Last updated | ✅ | yes | count of citations · `mission.updated_at` |

**Finding (the Gate working):** the Core provides *more* than assumed, but the advanced sections
(**Coverage · Framework · Exceptions/Gaps**) exist **only for Gap Assessment missions** (via the
`GapMatrix`). So the Result has **two shapes** — a full one (Gap Assessment) and a simpler one (every
other type: Executive Summary + Evidence + Export). We build **only on what exists**; advanced sections
render only where they are naturally derivable — never half a page on missing data.

**Framework decision (owner):** *not* added as a Mission/API field to please the UI. It is shown only
where it already exists naturally — inside the **Coverage** section of a Gap Assessment result — and
stays **out of the (universal) Trust Bar**.

---

## Builder Capability Gate — also **before any commit**

*Not only "what can the Core produce?" but "**is there one builder, or a family?**" The package already
has two: `build_deliverable` (generic, any mission) and `build_gap_matrix` (Gap Assessment only). That
is a **family of builders**, not one — so the choice must not be an `if mission.type == GAP` in the
route.*

**Decision — a builder registry in the Application layer** (route/presenter never branch on type):

```
ResultQuery.execute → DeliverableBuilderRegistry.builder_for(mission_type) → a DeliverableBuilder
                        ├── (default) GenericResultBuilder        → build_deliverable
                        └── gap_assessment → GapAssessmentResultBuilder → build_deliverable + build_gap_matrix
```

Even with one or two builders in S3, the registry is the seam: **S4/S5 add a `VendorAssessmentBuilder`
/ `PolicyReviewBuilder` by registering it — no change to the Route, the Presenter, or `ResultQuery`.**
The gap builder takes an injected `FrameworkLibrary` (loaded in the composition root, not the layer).

---

**Progress log**

- ✅ **Owner-approved** with 7 design rules + two Capability Gates (Core + Builder) answered before code.
- ✅ **Application read side built** (pure, `mission-application`), incl. owner rules 8–9: a **stable
  `ResultView`** (`mission_id · title · TrustBar · content`) + **polymorphic `ResultContent`**
  (`GenericContent` / `GapAssessmentContent`, each with a `kind`; the union grows, `ResultView` never
  does); per-section confidence on `ResultSectionView`; the `DeliverableBuilder` **protocol** +
  `DeliverableBuilderRegistry.for_mission(mission, mission_type)` (takes the whole mission — selection
  can grow past type); `ResultQuery` (`None`→404, `DeliverableNotReady`→409, else the selected
  builder). Concrete builders stay in the composition root (Use-Case boundary — no rendering/framework
  libs here). **Rule 10 applied:** the builder returns `ResultContent` (`build_content`); `ResultQuery`
  assembles the frame (Trust Bar + title) into the `ResultView` — one job per layer. 26 tests green
  (registry routing, 404, 409, and the query-assembled Trust Bar); ruff + mypy --strict clean.
- ✅ **Three more contracts locked (owner rules 11–13), pure + tested:** `DeliverableProvider` (the
  base Deliverable, abstracted) · `FrameworkProvider` (the framework source) · the **Export** service —
  `Exporter` (exports a **`ResultView`**) + `ExportService` (routes by format, `UnsupportedFormat`→400)
  + `ExportedFile`. Every Application external dependency is now a contract. 31 tests green.
- 🧊 **Application Contract Freeze declared** (`PRODUCT_DEVELOPMENT_PROCESS.md`): the Application-layer
  contract *language* is frozen — no new Protocol/Port/Builder unless implementation reveals an
  existing one is insufficient (anti-over-abstraction, the mirror of Product/Architecture Drift).
- ✅ **Backend built & integration-tested (grc-api, the composition root):** `BundledDeliverableProvider`
  (`build_deliverable`); `GenericResultBuilder(DeliverableProvider)`; `GapAssessmentResultBuilder(
  DeliverableProvider, FrameworkProvider)` — *enriches* the base with `build_gap_matrix`; `Markdown/
  Docx/Pdf` exporters rendering a **`ResultView`**; the registry + `ExportService` +
  `FrameworkLibrary.from_bundled()` wired in `create_app`; `GET …/deliverable` (`response_model=None`
  for the polymorphic content) + `…/export?format=`; errors mapped (`DeliverableNotReady`→409,
  `UnsupportedFormat`→400). **7 integration tests** drive a **real Gap Assessment mission** to
  completion (A.8.5 covered, A.8.24 a gap) → Result with **Trust Bar + 3 sections + a real coverage
  block** (framework, total 2, covered 1); no internals leak; 409 before Completed; 404 cross-tenant;
  **export md/pdf real bytes** (`%PDF…`); 400 on an unknown format. 30 grc-api tests green; ruff +
  mypy --strict clean. Only `grc-api` imports `deliverables`/`framework_library`.
- ✅ **Frontend Result page built & verified end-to-end (browser).** Rule 14 applied: `src/result/`
  = a **`ResultPresenterRegistry`** (`GenericContentView` / `GapContentView` + each presenter's
  `availableExports`) — the page never switches on `content.kind`; `useResult` (data via the client,
  no `fetch` in React); `ResultPage` renders the **fixed order** *Trust Bar → content → Export (last)*,
  labelled **"Result"** (never "Deliverable"), **no edit**. Verified live: opened a completed Gap
  Assessment's Result → Trust Bar (3 evidence · Human review · Updated) → **Coverage ISO/IEC 27001:2022
  50% (1/2)** + *Evidence Mapping* note → **Exceptions/Gaps A.8.24** → sections with citations → Export
  MD/DOCX/PDF; **PDF export → 200 OK** (fetched with auth, downloaded); no console errors; `tsc` clean.
- ✅ **Owner Design Review → Approved with changes, applied:** "View Result" → **"Open Result"**
  (product language, not CRUD); + the `ResultPresenter`-split future note recorded (above). **S3
  CLOSED** (owner sign-off 2026-07-22).

---

**Goal.** Turn a completed mission into a **Result** the user can trust and export — trust established
before content, content before download.

**User question (rule 11):** *"Can I rely on this result?"* · **Primary decision:** trust it / export it.

---

**Given / When / Then**

```
Given   a mission owned by tenant T that has reached Completed,
When    the user opens its Result (from the Work Surface's Deliverable tab, or a Results index),
Then    the page renders in the fixed order:
        • Trust Bar   — #evidence sources · human-review status · last updated (universal; honest —
                        "Evidence Mapping", never "compliance attestation"; framework NOT here);
        • Executive Summary — the headline the user acts on;
        • Coverage    — (Gap Assessment only) coverage % + framework, from the GapMatrix;
        • Evidence    — the cited sources (each opens its Document);
        • Exceptions / Gaps — (Gap Assessment only) the uncovered controls, surfaced not hidden;
        • Export      — LAST: download as md / docx / pdf (bytes).
And     there is NO edit affordance — a Result is derived, never edited (Principle 6);
And     the Result exists ONLY when the mission is Completed (else 409 / "available when complete");
And     a mission of another tenant resolves to 404 (fail-closed);
And     no tool/pipeline/chunk id appears — only human-readable content + citations.
```

---

**UX Metrics** (targets — a "No" is a finding)

- The Trust Bar is the **first** thing rendered; Export is the **last**.
- Clicks to open the Result from a completed mission: **1**.
- Clicks to verify a claim (open a citation → its Document): **1**.
- Cross-tenant leakage: **0**.

---

**APIs used** (from the REST API Contract — no invented endpoints; `deliverables` package backs them)

- `GET /v1/missions/{id}/deliverable` → the **derived** Result (sections · citations · coverage);
  `409` if the mission is not Completed. *(Domain name stays "deliverable"; the UI labels it "Result".)*
- `GET /v1/missions/{id}/deliverable/export?format=md|docx|pdf` → file **bytes** (no edit/PUT).

---

**Referenced Design Checklist** — View: **Deliverable / Result**

- **Gate 0** delete test: removing it breaks delivering (and trusting) the outcome.
- **Gate 1** user language ("Result", *Evidence Mapping*); "Deliverable" only in domain/API.
- **Gate 3/6** derived, **never edited** (no edit affordance); one question / one decision (trust→export).
- **Gate 5** every action ↔ a real endpoint (`deliverable`, `export`); `409` before Completed.
- **Gate 7** **Trust Bar first** (the new rule; `#sources · human-review · updated`) · citations on
  every claim · honest framing · **evidence-first, not prose-first** · tenant-scoped fail-closed.

---

**Done Definition**

- [ ] Given/When/Then hold; the page renders in the fixed order with the **Trust Bar first, Export
      last**; UX metrics met.
- [ ] `GET …/deliverable` returns the derived Result (View Model — no implementation internals),
      `409` before Completed, `404` cross-tenant (fail-closed).
- [ ] Export returns md/docx/pdf **bytes**; **no edit** path anywhere.
- [ ] Frontend **Result** view built on the **Presenter → Client** layering (no `fetch` in React);
      "Deliverable" never shown to the user.
- [ ] Tests green: `uv run pytest` · ruff · mypy --strict; a browser check of the full order.
- [ ] Design Review Checklist → **Approved** (block recorded); **Slice Retrospective** appended.
- [ ] **No Foundational Document edited** — unless implementation contradicts one (stop / fix / resume).

---

**Approval block**

```
View:      Deliverable / Result
Gates:     0✅ 1✅ 2✅ 3✅ 4✅ 5✅ 6✅ 7✅
Findings:  0 🔴 · 0 🟠 · 2 🟡 · 0 🔵   (owner review; both applied)
Status:    Approved with changes → applied & verified → Closed
Reviewer:  Product Owner (Design Review); Claude applied the changes
Date:      2026-07-22
Version:   S3 v2 (post-review)
```

*Owner-review findings (both applied):* 🟡 "View Result" → "Open Result" (product language) · 🟡 record
the `ResultPresenter`-split future note. No API/backend/Foundational change.

---

**Slice Retrospective** *(the Learning Unit)*

1. **Did we edit any Foundational Document? No** — the REST API's deliverable/export endpoints were used
   as-is; the Core was untouched. Two *deliberate governance additions* (not drift): the **Trust-Bar
   rule** in the Design Review Checklist and the **Application Contract Freeze**. The **Freeze held.**
2. **What did we learn?** (a) The Core provides **more** than assumed — the `GapMatrix` already carries
   framework · coverage · gaps, and `Section.confidence` exists (the *opposite* of S1/S2's finding — the
   Capability Gate caught it early). (b) The Application-layer language reached **saturation** → the
   Application Contract Freeze. (c) The frontend needs its **own registry** (the `ResultPresenterRegistry`)
   mirroring the backend — Open/Closed at the product level.
3. **Does this affect later slices?** **Yes:** a new *mission type* is now a new **builder + presenter**
   (both registries) with **no page/route/`ResultView` change** — the pattern is proven. `TrustBar`
   becomes a shared primitive at its second consumer.
4. **Decision:** **Close Slice** ✅ (owner sign-off 2026-07-22).
