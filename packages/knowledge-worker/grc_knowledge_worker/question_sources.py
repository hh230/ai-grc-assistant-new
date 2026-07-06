"""Combines the two disjoint sources the Knowledge Worker checks coverage over into one
unified question set the Gap Detector can evaluate: KI-P1's hand-curated
``/knowledge-catalog`` questions and KI-P3's deterministic, ontology-generated ones
(``generate_ontology_questions``). Neither source is modified here — this module only
merges them and defensively guards against an id collision between them. ADR-0027 already
guarantees the ontology's own generated ids are namespaced and disjoint from the curated
catalog, but a merge is the one place a violation of that guarantee would actually surface as
a silently dropped or overwritten question, so it is checked here rather than assumed.
"""

from __future__ import annotations

from grc_knowledge_intelligence import KnowledgeQuestion
from grc_knowledge_ontology import DomainOntology, generate_ontology_questions


def combine_question_sources(
    *,
    catalog_questions: tuple[KnowledgeQuestion, ...],
    ontology: DomainOntology,
) -> tuple[KnowledgeQuestion, ...]:
    """Every question the Knowledge Worker should check coverage for this cycle: the curated
    catalog plus everything the ontology can mechanically generate from its topics and
    contract types. Raises ``ValueError`` if any ``question_id`` appears more than once across
    the combined set.
    """
    generated = generate_ontology_questions(ontology)
    combined = tuple(catalog_questions) + generated

    ids = [question.question_id for question in combined]
    if len(ids) != len(set(ids)):
        duplicates = sorted({question_id for question_id in ids if ids.count(question_id) > 1})
        raise ValueError(
            "combine_question_sources produced duplicate question_id(s) between the curated "
            f"catalog and the ontology: {duplicates}"
        )
    return combined
