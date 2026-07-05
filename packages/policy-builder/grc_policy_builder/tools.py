"""Policy Builder's one Tool (CLAUDE.md §9-10): ``draft_policy_from_obligation.v1``. Read-only
(``ToolSideEffect.READ_ONLY``, which structurally sets ``requires_approval=False``) — not
because a policy draft is unimportant, but because this Tool never writes one anywhere. It
returns proposed text and nothing else; a human must explicitly take that proposal and save it
through the existing, already human-gated policy-authoring workflow (``POST /policies`` ->
``draft``, then the unchanged ``submit-for-review``/``approve``/``publish`` lifecycle) for a
policy to exist at all (ADR-0024). That is what "human approval required before any policy
change" means here by construction, not by a runtime check this Tool would have to enforce.

The Tool is the anti-corruption boundary (CLAUDE.md §15): it fetches the concrete obligation
record via ``ports.py``'s structural ``Protocol``s, translates it into ``models.py``'s plain
value object, and only then calls the pure ``drafting.draft_policy`` — the engine itself never
touches a database record.
"""

from __future__ import annotations

from grc_domain.platform import Permission, ToolDescriptor, ToolSideEffect
from grc_domain.shared.identifiers import ToolId
from grc_domain.shared.value_objects import SemanticVersion
from grc_tools import Tool, ToolContext, ToolOutcome
from pydantic import BaseModel

from .drafting import draft_policy
from .exceptions import ObligationNotFoundError
from .models import ObligationForDrafting
from .ports import ObligationStore, RawDocumentStore

_CONFIRMED_STATUS = "confirmed"

DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME = "draft_policy_from_obligation"
DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION = "1.0.0"


class DraftPolicyFromObligationInput(BaseModel):
    obligation_id: str


class PolicyDraftEvidence(BaseModel):
    """The proposed draft, with the evidence CLAUDE.md §19 requires and a full account of
    what still needs a human's judgment — never a claim of completeness."""

    obligation_id: str
    title: str
    body: str
    citation: str
    sections_requiring_human_input: list[str]


class DraftPolicyFromObligationOutput(BaseModel):
    draft: PolicyDraftEvidence


class DraftPolicyFromObligationTool(
    Tool[DraftPolicyFromObligationInput, DraftPolicyFromObligationOutput]
):
    """Drafts a starter policy from one confirmed regulatory obligation. Read-only: there is
    no code path here that creates, edits, or approves a policy. Platform-scope, like Policy
    Hunter's ``list_applicable_obligations`` — it never reads a tenant's policies, so it is
    not tenant-scoped either (ADR-0024)."""

    def __init__(self, *, obligations: ObligationStore, raw_documents: RawDocumentStore) -> None:
        self._obligations = obligations
        self._raw_documents = raw_documents
        self._descriptor = ToolDescriptor.register(
            id=ToolId("draft-policy-from-obligation"),
            name=DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
            version=SemanticVersion.parse(DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION),
            description=(
                "Drafts a starter policy addressing one confirmed regulatory obligation, for "
                "human review. Never writes a policy anywhere."
            ),
            side_effect=ToolSideEffect.READ_ONLY,
            required_permissions=frozenset({Permission("policy_builder")}),
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    @property
    def input_model(self) -> type[DraftPolicyFromObligationInput]:
        return DraftPolicyFromObligationInput

    @property
    def output_model(self) -> type[DraftPolicyFromObligationOutput]:
        return DraftPolicyFromObligationOutput

    async def run(
        self, input: DraftPolicyFromObligationInput, context: ToolContext
    ) -> ToolOutcome[DraftPolicyFromObligationOutput]:
        record = await self._obligations.get(input.obligation_id)
        if record is None or record.classification_status != _CONFIRMED_STATUS:
            raise ObligationNotFoundError(f"no confirmed obligation {input.obligation_id!r}")
        raw_document = await self._raw_documents.get(record.raw_document_id)
        if raw_document is None:  # pragma: no cover - defensive; the FK constraint prevents this
            raise ObligationNotFoundError(f"no confirmed obligation {input.obligation_id!r}")

        obligation = ObligationForDrafting(
            obligation_id=record.id,
            obligation_text=record.obligation_text,
            control_domain=record.control_domain,
            suggested_policy_title=record.suggested_policy_title,
            source_id=raw_document.source_id,
            source_url=raw_document.url,
        )
        draft = draft_policy(obligation)

        return ToolOutcome(
            output=DraftPolicyFromObligationOutput(
                draft=PolicyDraftEvidence(
                    obligation_id=draft.obligation_id,
                    title=draft.title,
                    body=draft.body,
                    citation=draft.citation,
                    sections_requiring_human_input=list(draft.sections_requiring_human_input),
                )
            ),
            citations=(draft.citation,),
        )
