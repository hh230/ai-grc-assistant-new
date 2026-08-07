"""The `QuestionGenerator` realization: Claude authoring a sector's interview, once (ADR 0067).

**Claude is responsible for the language, not for the truth.** It writes the questions; the engine
decides what the answers mean. That is not a convention here — `_FORBIDDEN_FIELDS` rejects the whole
response if a decision field appears in it, because a model that starts returning `maturity_level`
or `recommended_controls` has quietly taken over the part of the system that must stay auditable.

The prompt is a **versioned file** next to this module, never a literal in this code, and its
version is stored on every release it produces (`prompt_version`) alongside the model name and the
generator's commit — the three facts an auditor needs to ask "how was this question written?" a
year from now.

Generation happens **once per sector**. Every later customer in that sector reads the stored
release; no customer request reaches a model through this path.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import subprocess
from typing import Any

from pipeline_contracts import (
    Language,
    LLMRequest,
    PromptFamily,
    PromptSegment,
    ResponseContract,
    SegmentKind,
    SegmentRole,
)

from grc_api.llm_provider import LLMRole, build_generation_provider, resolve

LOGGER = logging.getLogger(__name__)

KNOWLEDGE_PROMPT_VERSION = "sector_questions.v1.ar"
_PROMPT_FILE = pathlib.Path(__file__).with_name("prompts") / f"{KNOWLEDGE_PROMPT_VERSION}.md"

# The vocabulary is the SCHEMA's, not this module's — `release_questions_type_renderable` in
# migration 0007 fixed it long before this generator existed. An earlier draft of this file invented
# `single_choice`/`multi_choice`/`number`, which the model dutifully produced and the CHECK
# constraint refused on the first real call. Two vocabularies for one concept is a translation layer
# waiting to be written; there is one, and it lives in the migration.
_QUESTION_TYPES = frozenset({"boolean", "enum", "multi_select", "numeric", "date", "text"})
# Both kinds of choice need at least two options — the rule was never about `enum` (migration 0016).
_CHOICE_TYPES = frozenset({"enum", "multi_select"})
_IMPORTANCE = frozenset({"critical", "high", "medium", "low"})
_QUESTION_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_ARABIC = re.compile(r"[؀-ۿ]")

# Fields that would make the model a decision-maker. Their presence fails the whole response rather
# than being dropped: silently discarding them would let the prompt drift into asking for them.
_FORBIDDEN_FIELDS = frozenset(
    {
        "maturity_level",
        "maturity_score",
        "risk_level",
        "risk_score",
        "compliance_status",
        "recommended_controls",
        "recommended_actions",
        "priority",
        "gap",
        "verdict",
    }
)

_MIN_QUESTIONS = 8
_MAX_QUESTIONS = 15

# Both numbers come from a real run, not from a guess.
#
# 25 questions of Arabic text — each with references, `why_we_ask` and evidence — overran 8000
# output tokens and arrived as JSON cut off mid-object. Arabic costs several tokens per word.
# Raising the budget to 24000 then hit the SDK's own refusal: a non-streaming request that large
# may take over ten minutes, and this adapter does not stream.
#
# So the ceiling on questions comes DOWN to what one call can carry, rather than the budget going
# up to whatever the ceiling implies. That is the right way round anyway: a sector interview of
# fifteen questions that a human reviews properly is worth more than twenty-five nobody reads, and
# a question that does not change which obligations apply has no business being asked.
_MAX_OUTPUT_TOKENS = 16000


class GeneratedKnowledgeRejected(ValueError):
    """The model's response is not usable. Raised instead of repairing it: a half-understood
    interview is worse than none, and the reviewer would have no way to see what was patched."""


def knowledge_generator_model() -> str:
    """The model name recorded on every release this deployment generates."""
    _, model = resolve(LLMRole.GOVERNANCE)
    return model or "unconfigured"


def generator_commit() -> str:
    """The commit of the code that built the request. Together with the model and the prompt
    version it is what makes a release reproducible rather than merely explainable."""
    override = (os.environ.get("GRC_GENERATOR_COMMIT") or "").strip()
    if override:
        return override
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=pathlib.Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 — a deployment from a tarball has no git; say so, don't crash
        return "unknown"


def _prompt_text() -> str:
    return _PROMPT_FILE.read_text(encoding="utf-8")


class ClaudeQuestionGenerator:
    """Asks the governance model for one sector's questions and validates every one before it can
    become a draft release."""

    def __init__(self, provider: Any, *, prompt: str | None = None) -> None:
        self._provider = provider
        self._prompt = prompt if prompt is not None else _prompt_text()

    def generate(self, *, industry_slug: str) -> list[dict[str, Any]]:
        request = LLMRequest(
            family=PromptFamily.TOOL,
            workflow="sector_questions",
            language=Language.ARABIC,
            segments=[
                PromptSegment(
                    role=SegmentRole.SYSTEM,
                    kind=SegmentKind.WORKFLOW,
                    title="sector question authoring",
                    content=self._prompt,
                    source=KNOWLEDGE_PROMPT_VERSION,
                ),
                PromptSegment(
                    role=SegmentRole.USER,
                    kind=SegmentKind.USER_REQUEST,
                    title="sector",
                    # The slug and nothing else. No customer data reaches this call — the whole
                    # point of generating once per sector is that no customer is in the request.
                    content=f"القطاع: {industry_slug}",
                ),
            ],
            response_contract=ResponseContract(
                workflow="sector_questions",
                required_sections=("questions",),
                required_citations=False,
                citation_style="",
                required_formatting=("json",),
                required_confidence=False,
                forbidden_outputs=tuple(sorted(_FORBIDDEN_FIELDS)),
            ),
            params={"temperature": 0.2, "max_output_tokens": _MAX_OUTPUT_TOKENS},
        )
        answer = self._provider.generate(request)
        # Checked BEFORE parsing. A truncated response is invalid JSON, so parsing it first would
        # report "the response is not JSON" — technically true and completely misleading about
        # what to do next, which is raise the budget rather than debug the model.
        if getattr(answer, "finish_reason", "") in ("max_tokens", "length"):
            raise GeneratedKnowledgeRejected(
                f"the model ran out of output budget ({_MAX_OUTPUT_TOKENS} tokens) and its answer "
                f"was cut off mid-JSON; nothing was stored"
            )
        questions = _parse(answer.text)
        LOGGER.info(
            "knowledge_generated: industry=%s questions=%d model=%s prompt=%s",
            industry_slug,
            len(questions),
            getattr(answer, "model", ""),
            KNOWLEDGE_PROMPT_VERSION,
        )
        return questions


def _parse(text: str) -> list[dict[str, Any]]:
    """Validate before use — the model's output is untrusted input, not control flow."""
    payload = _json_object(text)
    raw = payload.get("questions")
    if not isinstance(raw, list):
        raise GeneratedKnowledgeRejected("the response has no `questions` array")
    if not _MIN_QUESTIONS <= len(raw) <= _MAX_QUESTIONS:
        raise GeneratedKnowledgeRejected(
            f"{len(raw)} questions is outside the agreed {_MIN_QUESTIONS}–{_MAX_QUESTIONS}"
        )

    seen: set[str] = set()
    questions: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        questions.append(_question(item, index, seen))
    return questions


def _json_object(text: str) -> dict[str, Any]:
    """The model was told to return JSON only. A fenced block is tolerated because it is a
    formatting habit, not a different answer; prose around a JSON object is not."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped[stripped.index("\n") + 1 :] if "\n" in stripped else stripped
        if stripped.lstrip().startswith("json"):
            stripped = stripped.lstrip()[4:]
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise GeneratedKnowledgeRejected(f"the response is not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GeneratedKnowledgeRejected("the response is not a JSON object")
    return payload


def _question(item: Any, index: int, seen: set[str]) -> dict[str, Any]:
    where = f"question[{index}]"
    if not isinstance(item, dict):
        raise GeneratedKnowledgeRejected(f"{where} is not an object")

    trespass = sorted(_FORBIDDEN_FIELDS & set(item))
    if trespass:
        raise GeneratedKnowledgeRejected(
            f"{where} carries decision fields {trespass}: the model writes the question, the "
            f"engine decides what the answer means"
        )

    question_id = str(item.get("question_id", "")).strip()
    if not _QUESTION_ID.match(question_id):
        raise GeneratedKnowledgeRejected(f"{where} has an unusable question_id {question_id!r}")
    if question_id in seen:
        raise GeneratedKnowledgeRejected(f"{where} repeats question_id {question_id!r}")
    seen.add(question_id)

    text_ar = str(item.get("canonical_text_ar", "")).strip()
    if not text_ar:
        raise GeneratedKnowledgeRejected(f"{where} has no canonical_text_ar")
    if not _ARABIC.search(text_ar):
        # Arabic is the canonical language (ADR 0067). A question that arrives in English is not a
        # translation problem to fix downstream — it is the wrong artifact.
        raise GeneratedKnowledgeRejected(f"{where} is not in Arabic: {text_ar[:40]!r}")

    kind = str(item.get("type", "")).strip()
    if kind not in _QUESTION_TYPES:
        raise GeneratedKnowledgeRejected(f"{where} has type {kind!r}, not one of {_QUESTION_TYPES}")
    options = list(item.get("options") or [])
    if kind in _CHOICE_TYPES and len(options) < 2:
        raise GeneratedKnowledgeRejected(f"{where} is a {kind} with fewer than two options")

    importance = str(item.get("importance", "")).strip()
    if importance not in _IMPORTANCE:
        raise GeneratedKnowledgeRejected(f"{where} has importance {importance!r}")

    category = str(item.get("category", "")).strip()
    if not category:
        raise GeneratedKnowledgeRejected(f"{where} has no category")

    references = _references(item.get("references"), where)
    if not references:
        # The schema requires at least one (`release_questions_has_a_reference`). Refused here so a
        # reviewer is told which question is ungrounded, rather than being handed a constraint name.
        raise GeneratedKnowledgeRejected(
            f"{where} cites no framework: a question nothing requires is a question nobody has to "
            f"answer"
        )

    return {
        "question_id": question_id,
        "canonical_text_ar": text_ar,
        "type": kind,
        "options": options,
        "required": bool(item.get("required", True)),
        "category": category,
        "importance": importance,
        "references": references,
        "why_we_ask": str(item.get("why_we_ask", "")).strip(),
        "evidence_required": [str(e) for e in (item.get("evidence_required") or [])],
    }


def _references(raw: Any, where: str) -> list[dict[str, Any]]:
    references = []
    for reference in raw or []:
        if not isinstance(reference, dict) or not str(reference.get("framework", "")).strip():
            raise GeneratedKnowledgeRejected(f"{where} has a reference with no framework")
        clause = str(reference.get("clause") or "").strip()
        # An absent clause is allowed and a blank one is not stored as blank: `clause` is optional
        # precisely so the model is never pushed into inventing a number it does not know.
        framework = str(reference["framework"]).strip()
        references.append({"framework": framework, **({"clause": clause} if clause else {})})
    return references


def build_knowledge_question_generator() -> ClaudeQuestionGenerator | None:
    """The composition seam. `None` when this deployment configured no governance model — the route
    turns that into a `503` naming what is missing, never a stub that answers plausibly."""
    provider = build_generation_provider(LLMRole.GOVERNANCE)
    if provider is None:
        LOGGER.warning(
            "knowledge_generation_unconfigured: no governance model is configured, so sector "
            "knowledge cannot be authored in this deployment"
        )
        return None
    return ClaudeQuestionGenerator(provider)
