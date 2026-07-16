"""LLM contracts — the provider-agnostic request/response shapes of the generation stage.

`LLMRequest` is the complete, structured request some later phase hands to some LLM. It is
never a single string, and it names no provider.

    LLMRequest
      ├─ PromptSegment[]        ordered layers, each with a role + kind + source (versioned):
      │     System Prompt → Developer Instructions → Workflow Prompt →
      │     Policies → Context → User Request → Response Contract
      ├─ ResponseContract       required sections / citations / formatting / confidence / forbidden
      ├─ PromptMetrics          sizes, tokens, policies applied, language, prompt versions
      └─ params + warnings + valid

`messages()` collapses the layered segments into the conventional system+user shape any
provider can consume, while the segments preserve the full structure for audit and for
providers that support a distinct developer role.

`LLMMessage` is the provider-neutral chat message value object, and `Answer` is the
generation stage's output contract — what any `GenerationProvider` returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pipeline_contracts.serialization import dataclass_dict


class Language(str, Enum):
    ENGLISH = "en"
    ARABIC = "ar"
    MIXED = "mixed"


class SegmentRole(str, Enum):
    """Provider-neutral role. `messages()` folds SYSTEM+DEVELOPER into a system message and
    USER into a user message; a later adapter may instead emit a real developer message."""

    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"


class SegmentKind(str, Enum):
    IDENTITY = "identity"                       # the global Rasheed system prompt
    DEVELOPER_INSTRUCTIONS = "developer_instructions"
    WORKFLOW = "workflow"                       # the per-workflow template
    POLICIES = "policies"                       # the applied prompt policies
    CONTEXT = "context"                         # the rendered ContextPackage
    USER_REQUEST = "user_request"
    RESPONSE_CONTRACT = "response_contract"     # the expected-response spec


class PromptFamily(str, Enum):
    """Which kind of prompt this is. Only ANSWER is built this phase; the rest are the
    extensibility surface (agent / mission / tool / reflection / reviewer prompts)."""

    ANSWER = "answer"
    AGENT = "agent"
    MISSION = "mission"
    TOOL = "tool"
    REFLECTION = "reflection"
    REVIEWER = "reviewer"


@dataclass
class PromptSegment:
    """One layer of the prompt. `source` records the versioned artifact that produced it
    (e.g. `rasheed_system.v1`, `compliance_workflow.v1`) for reproducibility/audit."""

    role: SegmentRole
    kind: SegmentKind
    title: str
    content: str
    source: str = ""
    estimated_tokens: int = 0

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class ResponseContract:
    """What a compliant answer must look like — declared per workflow, rendered into the
    prompt *and* kept structured so a later answer-validation phase can check against it."""

    workflow: str
    required_sections: tuple[str, ...]
    required_citations: bool
    citation_style: str
    required_formatting: tuple[str, ...]
    required_confidence: bool
    forbidden_outputs: tuple[str, ...]

    def is_empty(self) -> bool:
        return not self.required_sections and not self.forbidden_outputs

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass
class PromptMetrics:
    prompt_chars: int = 0
    context_chars: int = 0
    estimated_tokens: int = 0
    system_tokens: int = 0
    context_tokens: int = 0
    segment_count: int = 0
    workflow: str = ""
    language: str = ""
    policies_applied: list[str] = field(default_factory=list)
    prompt_versions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class LLMMessage:
    """One provider-neutral chat message. Adapters translate this (or the plain-dict shape
    from `LLMRequest.messages()`) into whatever their provider's SDK expects."""

    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMRequest:
    """The provider-agnostic output: everything an LLM call needs except the provider."""

    family: PromptFamily
    workflow: str
    language: Language
    segments: list[PromptSegment]
    response_contract: ResponseContract
    metrics: PromptMetrics = field(default_factory=PromptMetrics)
    params: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    valid: bool = True

    def segment(self, kind: SegmentKind) -> PromptSegment | None:
        return next((s for s in self.segments if s.kind == kind), None)

    def _join(self, role: SegmentRole) -> str:
        return "\n\n".join(s.content for s in self.segments if s.role == role and s.content)

    def system_prompt(self) -> str:
        return self.segment(SegmentKind.IDENTITY).content if self.segment(SegmentKind.IDENTITY) else ""

    def messages(self) -> list[dict[str, str]]:
        """Fold the layered segments into the conventional system + user chat shape. System
        gathers everything that shapes behaviour (identity → developer → workflow → policies
        → contract); user carries the task payload (context → request)."""
        system = "\n\n".join(
            s.content for s in self.segments
            if s.role in (SegmentRole.SYSTEM, SegmentRole.DEVELOPER) and s.content
        )
        user = "\n\n".join(
            s.content for s in self.segments if s.role == SegmentRole.USER and s.content
        )
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        return messages

    def typed_messages(self) -> list[LLMMessage]:
        """The same fold as `messages()`, as immutable `LLMMessage` value objects."""
        return [LLMMessage(role=m["role"], content=m["content"]) for m in self.messages()]

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass
class Answer:
    """The generation stage's output contract: the model's text plus the provenance an
    audit needs (provider, model, usage). Produced by a `GenerationProvider`; carries no
    provider SDK types."""

    text: str
    provider: str = ""
    model: str = ""
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)
