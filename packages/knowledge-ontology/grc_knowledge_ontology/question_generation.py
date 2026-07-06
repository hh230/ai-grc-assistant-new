"""Deterministic, template-based question generation from the Domain Ontology — no LLM, the
same "reviewed set over runtime-generated" posture ADR-0025 already took for the hand-curated
``/knowledge-catalog``. Each ``KnowledgeDomain`` has a small, reviewable set of question
templates (data, not a prompt); a template is applied once per ontology ``Topic`` in that
domain, and the four contract-clause templates are applied once per ``ContractType``. The
result is additive to, and disjoint from, the hand-curated catalog: every generated
``question_id`` is namespaced by domain/topic (or contract type), never colliding with a
curated one.
"""

from __future__ import annotations

from grc_knowledge_intelligence import KnowledgeDomain, KnowledgeQuestion

from .models import ContractType, DomainOntology, Topic

# One or more question templates per domain, applied to every ontology Topic in that domain.
# A domain with no templates here (e.g. one not yet covered by the ontology) simply generates
# no questions — never a guess at a generic phrasing that might not fit.
_TOPIC_QUESTION_TEMPLATES: dict[KnowledgeDomain, tuple[str, ...]] = {
    KnowledgeDomain.GOVERNANCE: (
        "What {topic} practices should this organization establish?",
        "What committees or approvals are required for {topic}?",
    ),
    KnowledgeDomain.RISK_MANAGEMENT: (
        "What risks apply to {topic}?",
        "What controls mitigate risks related to {topic}?",
    ),
    KnowledgeDomain.COMPLIANCE: ("What compliance monitoring practices apply to {topic}?",),
    KnowledgeDomain.INTERNAL_CONTROLS: ("What controls should exist for {topic}?",),
    KnowledgeDomain.AUDIT: ("What audit evidence should be collected for {topic}?",),
    KnowledgeDomain.DATA_PROTECTION: ("What safeguards should exist for {topic}?",),
    KnowledgeDomain.CYBERSECURITY_GOVERNANCE: ("What controls should exist to govern {topic}?",),
}

# Applied once per ContractType — mirrors the four contract question archetypes named in
# ADR-0027's requirements (required clauses / risk / protection / compliance obligations).
_CONTRACT_TYPE_QUESTION_TEMPLATES: tuple[str, ...] = (
    "What clauses should exist in a {contract_type} contract?",
    "What risks does a {contract_type} contract typically create?",
    "What clauses protect the organization in a {contract_type} contract?",
    "What compliance obligations affect a {contract_type} contract?",
)


def generate_topic_questions(topic: Topic) -> tuple[KnowledgeQuestion, ...]:
    templates = _TOPIC_QUESTION_TEMPLATES.get(topic.domain, ())
    return tuple(
        KnowledgeQuestion(
            question_id=f"{topic.domain.value}.{topic.topic_id}.q{index}",
            question=template.format(topic=topic.name),
            domain=topic.domain,
            category=topic.topic_id,
        )
        for index, template in enumerate(templates, start=1)
    )


def generate_contract_type_questions(contract_type: ContractType) -> tuple[KnowledgeQuestion, ...]:
    return tuple(
        KnowledgeQuestion(
            question_id=f"contracts.{contract_type.contract_type_id}.q{index}",
            question=template.format(contract_type=contract_type.name),
            domain=KnowledgeDomain.CONTRACTS,
            category=contract_type.contract_type_id,
        )
        for index, template in enumerate(_CONTRACT_TYPE_QUESTION_TEMPLATES, start=1)
    )


def generate_ontology_questions(ontology: DomainOntology) -> tuple[KnowledgeQuestion, ...]:
    """Every question this ontology can mechanically generate: one set per topic (by domain)
    plus one set per contract type. Raises ``ValueError`` if two generated questions would
    share a ``question_id`` — a defensive check that only trips if two topics/contract types
    share an id, which ``build_ontology`` already forbids."""
    questions: list[KnowledgeQuestion] = []
    for topic in ontology.topics:
        questions.extend(generate_topic_questions(topic))
    for contract_type in ontology.contract_types:
        questions.extend(generate_contract_type_questions(contract_type))

    ids = [question.question_id for question in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("generate_ontology_questions produced a duplicate question_id")
    return tuple(questions)
