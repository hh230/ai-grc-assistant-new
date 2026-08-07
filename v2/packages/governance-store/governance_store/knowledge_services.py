"""Application Services for Sector Knowledge Packs (`docs/adr/0067-application-service-contract`).

> **An Application Service orchestrates; it never decides.**

Each one opens a transaction when it needs one, calls the repository, calls the domain, calls the
LLM, and returns the event its operation means. It computes nothing and picks no state transition
of its own. An `if` on **business meaning** belongs in the domain; an `if` on *whether a call
succeeded* is orchestration and belongs here.

Named for the business operation, never for the objects known. There is no `KnowledgeService`,
because a name like that answers "what does this know?" — and a class that knows about everything
eventually does everything.

Events are **returned, not dispatched**. Wiring a bus later changes the composition root and no
service. Until then the name still earns its place: it states what the operation means, once,
where the operation happens.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Event:
    """What happened, named. Carries only what a subscriber needs to act."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Outcome:
    """The result of one use case: whether it changed anything, and what that means.

    `changed=False` is not an error. Every guarded write in the repository is idempotent, so a
    repeated submit or a second approval is a no-op — and whether *that* is a problem is the
    caller's judgement, not this layer's.
    """

    changed: bool
    event: Event | None = None
    data: dict[str, Any] = field(default_factory=dict)


class QuestionGenerator(Protocol):
    """The LLM, behind a port. Returns validated question dicts; it decides nothing else."""

    def generate(self, *, industry_slug: str) -> list[dict[str, Any]]: ...


# ── who may govern knowledge ─────────────────────────────────────────────────────────────────

KNOWLEDGE_APPROVER_ROLE = "knowledge_approver"


class NotAuthorized(Exception):
    """The caller does not hold the role this operation requires."""


@dataclass(frozen=True)
class Actor:
    """Who is asking, as established by authentication — never a name the caller typed.

    Every knowledge operation records its actor (`created_by`, `approved_by`, `activated_by`), and
    those columns are what an auditor reads a year from now. Taking the actor as a free string
    would let a caller write any name into them.
    """

    principal_id: str
    roles: tuple[str, ...] = ()


def require_knowledge_approver(actor: Actor, operation: str) -> None:
    """The one authorization rule in this layer, enforced where ADR 0054 puts it — the Application
    layer, not the route. The *policy* (which role governs knowledge) is the constant above; this
    only enforces it, which is why the services still decide nothing.

    Public, because the same rule guards the review console's *reads*: a draft is unreviewed
    knowledge, and reading one is as much a knowledge-governance act as approving it.

    Knowledge is platform-wide: one release serves every customer in a sector. A tenant role can
    therefore never be sufficient here — the blast radius of a bad release is all of them.
    """
    if KNOWLEDGE_APPROVER_ROLE not in actor.roles:
        raise NotAuthorized(f"{operation} requires the {KNOWLEDGE_APPROVER_ROLE} role")


# ── knowledge ────────────────────────────────────────────────────────────────────────────────


class GenerateKnowledgeTemplate:
    """`ensure_template` → LLM → `create_release`. Emits `KnowledgeTemplateGenerated`.

    The three calls exist because generation needs a container to hang off, content to store, and
    a version to be given. The transaction is `create_release`'s own — deliberately NOT opened
    here, because holding one across an LLM call would keep a row locked for the length of a
    network round trip to another company.
    """

    def __init__(
        self,
        store: Any,
        generator: QuestionGenerator,
        *,
        new_id: Callable[[], str],
        model: str,
        prompt_version: str,
        generator_commit: str,
    ) -> None:
        self._store = store
        self._generator = generator
        self._new_id = new_id
        self._model = model
        self._prompt_version = prompt_version
        self._generator_commit = generator_commit

    def __call__(self, *, industry_slug: str, actor: Actor) -> Outcome:
        require_knowledge_approver(actor, "generating a knowledge template")
        template = self._store.ensure_template(self._new_id(), industry_slug)
        questions = self._generator.generate(industry_slug=industry_slug)
        release_id = self._new_id()
        version = self._store.create_release(
            release_id=release_id,
            template_id=template["id"],
            questions=questions,
            generated_by_model=self._model,
            prompt_version=self._prompt_version,
            generator_commit=self._generator_commit,
            created_by=actor.principal_id,
        )
        return Outcome(
            changed=True,
            event=Event(
                "KnowledgeTemplateGenerated",
                {
                    "industry_slug": industry_slug,
                    "release_id": release_id,
                    "version": version,
                    "question_count": len(questions),
                    # The provenance travels with the event: a subscriber asking "where did this
                    # come from?" should not have to read the row back.
                    "generated_by_model": self._model,
                    "prompt_version": self._prompt_version,
                    "generator_commit": self._generator_commit,
                },
            ),
            data={"release_id": release_id, "version": version},
        )


class SubmitKnowledgeTemplate:
    """`submit_for_review`. Emits `KnowledgeTemplateSubmitted`.

    One guarded write, already atomic — an explicit transaction here would add a boundary that
    guarantees nothing. The service exists because this is where the use case and its event live.
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    def __call__(self, *, release_id: str, actor: Actor) -> Outcome:
        require_knowledge_approver(actor, "submitting a knowledge template for review")
        changed = self._store.submit_for_review(release_id)
        return Outcome(
            changed=changed,
            event=Event(
                "KnowledgeTemplateSubmitted",
                {"release_id": release_id, "submitted_by": actor.principal_id},
            )
            if changed
            else None,
        )


class ApproveKnowledgeTemplate:
    """`approve_release`. Emits `KnowledgeTemplateApproved`."""

    def __init__(self, store: Any, *, now: Callable[[], Any]) -> None:
        self._store = store
        self._now = now

    def __call__(self, *, release_id: str, actor: Actor) -> Outcome:
        require_knowledge_approver(actor, "approving a knowledge template")
        changed = self._store.approve_release(
            release_id, approver=actor.principal_id, at=self._now()
        )
        return Outcome(
            changed=changed,
            event=Event(
                "KnowledgeTemplateApproved",
                {"release_id": release_id, "approved_by": actor.principal_id},
            )
            if changed
            else None,
        )


class RejectKnowledgeTemplate:
    """`reject_release`. Emits `KnowledgeTemplateRejected`."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def __call__(self, *, release_id: str, actor: Actor) -> Outcome:
        require_knowledge_approver(actor, "rejecting a knowledge template")
        changed = self._store.reject_release(release_id)
        return Outcome(
            changed=changed,
            event=Event(
                "KnowledgeTemplateRejected",
                {"release_id": release_id, "rejected_by": actor.principal_id},
            )
            if changed
            else None,
        )


class PublishKnowledgeTemplate:
    """`mark_released`. Emits `KnowledgeTemplatePublished`.

    Publishing makes a release *eligible* for activation; it does not activate it. Keeping the two
    apart is what lets several releases be published while exactly one is live.
    """

    def __init__(self, store: Any, *, now: Callable[[], Any]) -> None:
        self._store = store
        self._now = now

    def __call__(self, *, release_id: str, actor: Actor) -> Outcome:
        require_knowledge_approver(actor, "publishing a knowledge template")
        changed = self._store.mark_released(release_id, at=self._now())
        return Outcome(
            changed=changed,
            event=Event(
                "KnowledgeTemplatePublished",
                {"release_id": release_id, "published_by": actor.principal_id},
            )
            if changed
            else None,
        )


class ActivateKnowledgeRelease:
    """`set_active_release`. Emits `ActiveReleaseChanged`. This is also rollback.

    Deliberately does **not** check that the release is releasable. The composite foreign key does,
    exactly: activating something never released is unrepresentable. Re-checking here would be a
    second, weaker copy of a rule the database already states precisely.
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    def __call__(
        self, *, industry_slug: str, release_id: str, actor: Actor, reason: str = ""
    ) -> Outcome:
        require_knowledge_approver(actor, "activating a knowledge release")
        previous = self._store.set_active_release(
            industry_slug=industry_slug,
            release_id=release_id,
            actor=actor.principal_id,
            reason=reason,
        )
        return Outcome(
            changed=True,
            event=Event(
                "ActiveReleaseChanged",
                {
                    "industry_slug": industry_slug,
                    "release_id": release_id,
                    # What it replaced. A first activation and a rollback are the same call and
                    # read identically without it.
                    "previous_release_id": previous,
                    "activated_by": actor.principal_id,
                    "reason": reason,
                },
            ),
            data={"previous_release_id": previous},
        )


class RetireIndustry:
    """`set_active_release(None)` → `set_industry_status` → `retire_release`. Emits
    `IndustryRetired`.

    The case that proved this layer exists, and the order matters. The schema refuses to demote a
    release while it is the active one — deliberately, so a release cannot be withdrawn underneath
    customers being interviewed on it. Retiring an industry therefore has a sequence: stop serving
    the release, mark the industry unavailable, then retire the release. One transaction, so a
    crash between them cannot leave an industry that is retired but still serving interviews.

    That ordering is not this service inventing a rule. The schema exposed an invariant we had
    forgotten to model explicitly — a schema creates no business rules, it only refuses a state
    that was already outside the domain — and stating the sequence here is what modelling it looks
    like. That is exactly the kind of coordination a service exists for.
    """

    def __init__(self, store: Any, *, connection: Any) -> None:
        self._store = store
        self._conn = connection

    def __call__(self, *, industry_slug: str, actor: Actor) -> Outcome:
        require_knowledge_approver(actor, "retiring an industry")
        with self._conn.transaction():
            was_active = self._store.set_active_release(
                industry_slug=industry_slug,
                release_id=None,
                actor=actor.principal_id,
                reason="industry retired",
            )
            changed = self._store.set_industry_status(industry_slug, "retired")
            if was_active is not None:
                self._store.retire_release(was_active, target_status="deprecated")
        return Outcome(
            changed=changed,
            event=Event(
                "IndustryRetired",
                {
                    "industry_slug": industry_slug,
                    "retired_release_id": was_active,
                    "retired_by": actor.principal_id,
                },
            )
            if changed
            else None,
            data={"retired_release_id": was_active},
        )


# ── assessments ──────────────────────────────────────────────────────────────────────────────


class StartAssessment:
    """`open_assessment` → `record_selection`. Emits `AssessmentStarted`.

    Does **not** choose the template. `primary_activity` suggests the active release and a human
    may override it with several; both arrive as arguments. "If no selection was given, use the
    active one" would be a business rule hidden in the orchestration layer, so the caller resolves
    it and this records what was decided alongside what was suggested.

    One transaction: an assessment with no selection cannot be interviewed, and one that exists
    without one is a row nobody can explain.
    """

    def __init__(self, store: Any, *, connection: Any, new_id: Callable[[], str]) -> None:
        self._store = store
        self._conn = connection
        self._new_id = new_id

    def __call__(
        self,
        *,
        tenant_id: str,
        organization_id: str,
        suggested_industry_slug: str | None,
        selected_release_ids: list[str],
        selected_by: str,
        source_session_id: str | None = None,
    ) -> Outcome:
        assessment_id = self._new_id()
        with self._conn.transaction():
            self._store.open_assessment(
                assessment_id=assessment_id,
                tenant_id=tenant_id,
                organization_id=organization_id,
                source_session_id=source_session_id,
            )
            self._store.record_selection(
                assessment_id=assessment_id,
                tenant_id=tenant_id,
                suggested_industry_slug=suggested_industry_slug,
                selected_release_ids=selected_release_ids,
                selected_by=selected_by,
            )
        return Outcome(
            changed=True,
            event=Event(
                "AssessmentStarted",
                {
                    "assessment_id": assessment_id,
                    "tenant_id": tenant_id,
                    "organization_id": organization_id,
                    "selected_release_ids": list(selected_release_ids),
                    # Whether the human kept the suggestion is a fact worth carrying: a suggestion
                    # someone accepted and one nobody examined look identical without it.
                    "suggested_industry_slug": suggested_industry_slug,
                },
            ),
            data={"assessment_id": assessment_id},
        )


class RecordSectorAnswers:
    """`save_sector_answers`. Emits `SectorAnswersRecorded`.

    The repository already owns the transaction — the answer set is written whole or not at all —
    so this must not open a second one around it.
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    def __call__(
        self, *, assessment_id: str, tenant_id: str, answers: list[dict[str, Any]]
    ) -> Outcome:
        self._store.save_sector_answers(
            assessment_id=assessment_id, tenant_id=tenant_id, answers=answers
        )
        return Outcome(
            changed=True,
            event=Event(
                "SectorAnswersRecorded",
                {"assessment_id": assessment_id, "answer_count": len(answers)},
            ),
        )


class CompleteAssessment:
    """`complete_assessment`. Emits `AssessmentCompleted`.

    The most consequential event here: after it, the schema refuses every further write to this
    assessment, which is what lets a plan be built from it without snapshot isolation.
    """

    def __init__(self, store: Any, *, now: Callable[[], Any]) -> None:
        self._store = store
        self._now = now

    def __call__(self, *, assessment_id: str, tenant_id: str) -> Outcome:
        changed = self._store.complete_assessment(
            assessment_id, tenant_id=tenant_id, at=self._now()
        )
        return Outcome(
            changed=changed,
            event=Event(
                "AssessmentCompleted", {"assessment_id": assessment_id, "tenant_id": tenant_id}
            )
            if changed
            else None,
        )


class SessionReader(Protocol):
    """The concluded discovery session, behind a port. Only what resolving a sector interview needs
    — deliberately not the whole discovery package, so this layer never imports it."""

    def get_session(self, session_id: str, tenant_id: str) -> Any: ...


PRIMARY_ACTIVITY_SIGNAL = "primary_activity"


class OpenSectorInterview:
    """`find_assessment_for_session` → `get_active_release` → `StartAssessment`. Emits
    `AssessmentStarted` (via the service it composes) or nothing at all.

    This is the caller `StartAssessment` deliberately refuses to be. `StartAssessment` does not
    choose a template because "if no selection was given, use the active one" would be a business
    rule hidden in orchestration — so the resolution lives here, in the open, where it can be read:
    the customer's `primary_activity` SUGGESTS a sector, the sector's activation pointer decides
    which release is live, and both are recorded so an accepted suggestion and an unexamined one
    stay distinguishable.

    Three outcomes, and only one of them is a failure:

        already_open   this session already opened an assessment — returned, not duplicated
        no_sector_pack the sector has nothing activated, or the customer named no sector at all
        opened         a new assessment, citing exactly the release that was live at this moment

    `no_sector_pack` is a NORMAL state with `changed=False`, not an error. Most sectors will have no
    published pack for a long time, and a customer must still be able to finish their assessment —
    the alternative is a product that refuses to work until every sector is authored.
    """

    def __init__(
        self,
        store: Any,
        sessions: SessionReader,
        *,
        connection: Any,
        new_id: Callable[[], str],
    ) -> None:
        self._store = store
        self._sessions = sessions
        self._start = StartAssessment(store, connection=connection, new_id=new_id)

    def __call__(self, *, session_id: str, tenant_id: str, organization_id: str) -> Outcome:
        existing = self._store.find_assessment_for_session(session_id, tenant_id=tenant_id)
        if existing is not None:
            # The release this assessment CITES, not whatever is live now. A reviewer may have
            # rolled the pointer forward mid-interview, and answering half a questionnaire against
            # one release and half against another is not an interview anyone can interpret.
            selection = self._store.get_selection(existing["id"], tenant_id=tenant_id)
            cited = (selection or {}).get("selected_release_ids") or []
            return Outcome(
                changed=False,
                data={
                    "status": "already_open",
                    "assessment_id": existing["id"],
                    "release_id": cited[0] if cited else None,
                    "suggested_industry_slug": (selection or {}).get("suggested_industry_slug"),
                    "completed_at": existing["completed_at"],
                },
            )

        session = self._sessions.get_session(session_id, tenant_id)
        # Two different failures, said differently. Collapsing them cost an hour once: a test read
        # the right session id from the wrong database and was told it "has not concluded".
        if session is None:
            raise ValueError(f"no discovery session {session_id!r} for this tenant")
        if getattr(session, "status", "") != "concluded":
            raise ValueError(
                f"discovery session {session_id!r} has not concluded; a sector interview is opened "
                f"from what the core interview established, not before it"
            )

        industry_slug = session.signals.value(PRIMARY_ACTIVITY_SIGNAL)
        release = (
            self._store.get_active_release(industry_slug) if industry_slug else None
        )
        if release is None:
            return Outcome(
                changed=False,
                data={"status": "no_sector_pack", "suggested_industry_slug": industry_slug},
            )

        outcome = self._start(
            tenant_id=tenant_id,
            organization_id=organization_id,
            suggested_industry_slug=industry_slug,
            selected_release_ids=[release["id"]],
            selected_by=tenant_id,
            source_session_id=session_id,
        )
        return Outcome(
            changed=True,
            event=outcome.event,
            data={
                "status": "opened",
                "assessment_id": outcome.data["assessment_id"],
                "release_id": release["id"],
                "suggested_industry_slug": industry_slug,
                "completed_at": None,
            },
        )
