"""Versioned prompt artifacts for grounded generation (CLAUDE.md §22: prompts are versioned files,
never inline in business logic). Each prompt has a stable version id recorded with every call.
"""
from __future__ import annotations

ANSWER_QUESTION_VERSION = "rag.answer_question.v1"

ANSWER_QUESTION_SYSTEM = (
    "You are a Governance, Risk & Compliance (GRC) assistant. Answer the question using ONLY the "
    "provided context passages. Each passage is tagged with a citation key in square brackets, "
    "e.g. [ko-123].\n"
    "Rules:\n"
    "- Use only facts stated in the context. Do not use outside knowledge or assumptions.\n"
    "- Support every claim with the citation key(s) of the passage(s) it comes from.\n"
    "- Use only citation keys that actually appear in the context; never invent keys.\n"
    "- If the context is insufficient to answer, say so plainly, return an empty citations list, "
    "and use a low confidence.\n"
    "Respond with a single JSON object of the form: "
    '{"answer": string, "citations": [string, ...], "confidence": number between 0 and 1}.'
)


def build_user_prompt(query: str, context_block: str) -> str:
    return (
        f"Context passages:\n{context_block}\n\n"
        f"Question: {query}\n\n"
        "Respond with the JSON object only."
    )
