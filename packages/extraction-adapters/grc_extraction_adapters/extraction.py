"""A rule-based normative extractor (implements ``ExtractorPort``).

Produces candidate knowledge objects from a segment using deontic/definition cues — ``shall``/
``must`` → a mandatory requirement, ``should`` → a recommended one, ``X means …`` → a definition —
each carrying full provenance (anchor, span) so the fact is reproducible. This is the ``RULE``
technique; an AI-assisted extractor would implement the identical port (CLAUDE.md §11–12). The
engine treats both the same.
"""
from __future__ import annotations

import re

from grc_domain.extraction import ExtractionCandidate
from grc_domain.knowledge import (
    DefinitionPayload,
    KnowledgeObjectType,
    NormativeStrength,
    ProvenanceRecord,
    RequirementPayload,
)
from grc_domain.shared.value_objects import Confidence
from grc_extraction import (
    CandidateSet,
    ExtractionContext,
    ExtractorDescriptor,
    ExtractorPort,
    ExtractorTechnique,
    Segment,
)

_DEFINITION_CUE = re.compile(r"\bmeans\b", re.IGNORECASE)
_QUOTED_TERM = re.compile(r"[\"“'‘]([^\"”'’]+)[\"”'’]\s+means\b", re.IGNORECASE)
_MANDATORY_CUE = re.compile(r"\b(shall|must)\b", re.IGNORECASE)
_RECOMMENDED_CUE = re.compile(r"\bshould\b", re.IGNORECASE)

_MANDATORY_CONFIDENCE = 0.9
_RECOMMENDED_CONFIDENCE = 0.72
_DEFINITION_CONFIDENCE = 0.85


class RuleBasedNormativeExtractor(ExtractorPort):
    """Extracts requirements and definitions from a segment via deterministic rules."""

    NAME = "rule-based-normative"
    VERSION = "1.0.0"

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            name=self.NAME,
            version=self.VERSION,
            technique=ExtractorTechnique.RULE,
            produces=frozenset({KnowledgeObjectType.REQUIREMENT, KnowledgeObjectType.DEFINITION}),
            description="Deontic/definition cue extractor (shall/must/should/means).",
        )

    async def extract(self, segment: Segment, context: ExtractionContext) -> CandidateSet:
        candidates: list[ExtractionCandidate] = []

        term = _definition_term(segment.text)
        if term is not None:
            candidates.append(
                self._candidate(
                    segment,
                    context,
                    object_type=KnowledgeObjectType.DEFINITION,
                    confidence=_DEFINITION_CONFIDENCE,
                    normative_strength=NormativeStrength.INFORMATIVE,
                    payload=DefinitionPayload(term=term),
                )
            )

        modal = _modal(segment.text)
        if modal is not None:
            strength = (
                NormativeStrength.MANDATORY
                if modal in ("shall", "must")
                else NormativeStrength.RECOMMENDED
            )
            confidence = (
                _MANDATORY_CONFIDENCE
                if strength is NormativeStrength.MANDATORY
                else _RECOMMENDED_CONFIDENCE
            )
            candidates.append(
                self._candidate(
                    segment,
                    context,
                    object_type=KnowledgeObjectType.REQUIREMENT,
                    confidence=confidence,
                    normative_strength=strength,
                    payload=RequirementPayload(modal=modal),
                )
            )

        return CandidateSet(objects=tuple(candidates))

    def _candidate(
        self,
        segment: Segment,
        context: ExtractionContext,
        *,
        object_type: KnowledgeObjectType,
        confidence: float,
        normative_strength: NormativeStrength,
        payload: DefinitionPayload | RequirementPayload,
    ) -> ExtractionCandidate:
        confidence_value = Confidence(confidence)
        provenance = ProvenanceRecord(
            source_version_id=context.version_id,
            anchor=segment.anchor,
            text_span=segment.text_span,
            page_range=segment.page_range,
            extractor_name=self.NAME,
            extractor_version=self.VERSION,
            confidence=confidence_value,
            language=context.language,
        )
        return ExtractionCandidate(
            object_type=object_type,
            stable_key=f"{segment.anchor}::{object_type.value}",
            verbatim_text=segment.text,
            provenance=provenance,
            normative_strength=normative_strength,
            language=context.language,
            confidence=confidence_value,
            payload=payload,
            extractor_name=self.NAME,
            extractor_version=self.VERSION,
        )


def _modal(text: str) -> str | None:
    mandatory = _MANDATORY_CUE.search(text)
    if mandatory is not None:
        return mandatory.group(1).lower()
    recommended = _RECOMMENDED_CUE.search(text)
    if recommended is not None:
        return "should"
    return None


def _definition_term(text: str) -> str | None:
    quoted = _QUOTED_TERM.search(text)
    if quoted is not None:
        return quoted.group(1).strip() or None
    if _DEFINITION_CUE.search(text) is None:
        return None
    before = _DEFINITION_CUE.split(text, maxsplit=1)[0].strip()
    if not before:
        return None
    return " ".join(before.split()[-6:]) or None
