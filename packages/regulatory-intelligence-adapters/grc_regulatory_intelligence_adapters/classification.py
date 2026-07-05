"""The LLM classifier: a first-class ``grc_tools.Tool`` plus the ``ObligationClassifierPort``
adapter that calls it *through the Tool Registry* — so every classification call is
authorized, validated, and unconditionally audited exactly like any other Tool invocation
(CLAUDE.md §9, §19), never a raw, unaudited LLM SDK call from business logic (CLAUDE.md §7).
"""

from __future__ import annotations

import json

from grc_domain.platform import Permission, ToolDescriptor, ToolSideEffect
from grc_domain.shared.identifiers import ToolId
from grc_domain.shared.value_objects import SemanticVersion
from grc_llm import ChatMessage, ChatModel, ChatRequest
from grc_regulatory_intelligence import (
    ControlDomain,
    ObligationCandidate,
    ObligationClassification,
    ObligationClassificationError,
    ObligationClassifierPort,
    ObligationType,
    RawRegulatoryDocument,
    Severity,
)
from grc_tools import (
    Tool,
    ToolContext,
    ToolInputValidationError,
    ToolOutcome,
    ToolPermissionDeniedError,
    ToolRegistry,
)
from pydantic import BaseModel, ValidationError, field_validator

from .exceptions import ClassificationRejectedError
from .prompts import (
    CLASSIFY_REGULATORY_OBLIGATION_SYSTEM,
    CLASSIFY_REGULATORY_OBLIGATION_VERSION,
    build_user_prompt,
)

TOOL_NAME = "classify_regulatory_obligation"
TOOL_VERSION = "1.0.0"

_OBLIGATION_TYPES = frozenset(member.value for member in ObligationType)
_CONTROL_DOMAINS = frozenset(member.value for member in ControlDomain)
_SEVERITIES = frozenset(member.value for member in Severity)


class ClassifyObligationInput(BaseModel):
    """Tool input: the candidate text plus its source, for grounding the classifier's prompt."""

    obligation_text: str
    source_id: str


class _RawClassificationPayload(BaseModel):
    """The LLM's own JSON, validated strictly against the classification vocabulary. Any
    field missing, misspelled, or outside the declared vocabulary raises ``ValidationError``
    — malformed or unsupported classifications are rejected here, before they ever become a
    stored obligation."""

    obligation_type: str
    control_domain: str
    suggested_policy_title: str
    severity: str
    confidence: float

    @field_validator("obligation_type")
    @classmethod
    def _known_obligation_type(cls, value: str) -> str:
        if value not in _OBLIGATION_TYPES:
            raise ValueError(f"unsupported obligation_type: {value!r}")
        return value

    @field_validator("control_domain")
    @classmethod
    def _known_control_domain(cls, value: str) -> str:
        if value not in _CONTROL_DOMAINS:
            raise ValueError(f"unsupported control_domain: {value!r}")
        return value

    @field_validator("severity")
    @classmethod
    def _known_severity(cls, value: str) -> str:
        if value not in _SEVERITIES:
            raise ValueError(f"unsupported severity: {value!r}")
        return value

    @field_validator("suggested_policy_title")
    @classmethod
    def _non_empty_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("suggested_policy_title must not be empty")
        return value

    @field_validator("confidence")
    @classmethod
    def _confidence_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be within [0, 1]")
        return value


class ClassifyObligationOutput(BaseModel):
    """Tool output: the validated classification plus the model/prompt provenance that
    produced it (so a caller can reconstruct full grounding from ``ToolRegistry.invoke``'s
    return value alone, without reaching back into the audit log)."""

    obligation_type: str
    control_domain: str
    suggested_policy_title: str
    severity: str
    confidence: float
    classifier_model: str
    prompt_version: str


class ClassifyRegulatoryObligationTool(Tool[ClassifyObligationInput, ClassifyObligationOutput]):
    """Classifies one regulatory obligation via the provider-agnostic ``ChatModel``. Read-only
    (no side effects) — it only proposes a classification; nothing is persisted here."""

    def __init__(self, chat: ChatModel) -> None:
        self._chat = chat
        self._descriptor = ToolDescriptor.register(
            id=ToolId("classify-regulatory-obligation"),
            name=TOOL_NAME,
            version=SemanticVersion.parse(TOOL_VERSION),
            description=(
                "Classifies one regulatory obligation into obligation type, control domain, "
                "suggested policy title, and severity, with a confidence score."
            ),
            side_effect=ToolSideEffect.READ_ONLY,
            required_permissions=frozenset({Permission("regulatory_intelligence")}),
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    @property
    def input_model(self) -> type[ClassifyObligationInput]:
        return ClassifyObligationInput

    @property
    def output_model(self) -> type[ClassifyObligationOutput]:
        return ClassifyObligationOutput

    async def run(
        self, input: ClassifyObligationInput, context: ToolContext
    ) -> ToolOutcome[ClassifyObligationOutput]:
        request = ChatRequest(
            messages=(
                ChatMessage.system(CLASSIFY_REGULATORY_OBLIGATION_SYSTEM),
                ChatMessage.user(
                    build_user_prompt(input.obligation_text, source_id=input.source_id)
                ),
            ),
            json_object=True,
            temperature=0.0,
            prompt_version=CLASSIFY_REGULATORY_OBLIGATION_VERSION,
        )
        result = await self._chat.complete(request)

        try:
            data = json.loads(result.text)
        except json.JSONDecodeError as exc:
            raise ClassificationRejectedError(
                f"classifier returned non-JSON output: {exc}"
            ) from exc

        try:
            payload = _RawClassificationPayload.model_validate(data)
        except ValidationError as exc:
            raise ClassificationRejectedError(
                f"classifier returned an unsupported classification: {exc}"
            ) from exc

        output = ClassifyObligationOutput(
            **payload.model_dump(),
            classifier_model=result.model,
            prompt_version=CLASSIFY_REGULATORY_OBLIGATION_VERSION,
        )
        return ToolOutcome(
            output=output,
            confidence=output.confidence,
            model=result.model,
            prompt_version=CLASSIFY_REGULATORY_OBLIGATION_VERSION,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
        )


class LlmObligationClassifier(ObligationClassifierPort):
    """The pure engine's ``ObligationClassifierPort``, implemented by invoking
    ``ClassifyRegulatoryObligationTool`` through the Tool Registry — the registry authorizes,
    validates, executes, and unconditionally audits the call (including a rejected/failed
    classification), exactly as CLAUDE.md §19 requires for every AI action.
    """

    def __init__(self, registry: ToolRegistry, *, context: ToolContext) -> None:
        self._registry = registry
        self._context = context

    async def classify(
        self, candidate: ObligationCandidate, *, document: RawRegulatoryDocument
    ) -> ObligationClassification:
        try:
            output = await self._registry.invoke(
                TOOL_NAME,
                TOOL_VERSION,
                {"obligation_text": candidate.obligation_text, "source_id": document.source_id},
                self._context,
            )
        except (
            ToolInputValidationError,
            ToolPermissionDeniedError,
            ClassificationRejectedError,
        ) as exc:
            raise ObligationClassificationError(str(exc)) from exc

        if not isinstance(output, ClassifyObligationOutput):  # pragma: no cover - defensive
            raise ObligationClassificationError(
                f"unexpected classifier output type: {type(output)!r}"
            )

        return ObligationClassification(
            obligation_type=ObligationType(output.obligation_type),
            control_domain=ControlDomain(output.control_domain),
            suggested_policy_title=output.suggested_policy_title,
            severity=Severity(output.severity),
            confidence=output.confidence,
            classifier_model=output.classifier_model,
            prompt_version=output.prompt_version,
        )
