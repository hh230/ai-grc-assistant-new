"""Runs the Retrieval Engine against the real 117-document corpus and prints the retrieved
citations for 50 GRC queries (Arabic and English). Loads the in-memory providers from the
generated artifacts. Illustration only — not part of the engine.

Usage: python -m retrieval_engine.demo
"""

from __future__ import annotations

import time
from pathlib import Path

from retrieval_engine import Filter, RetrievalEngine, RetrievalQuery
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider

_V2 = Path(__file__).resolve().parents[3]
CHUNKS_DIR = _V2 / "knowledge" / "chunks"
EMBEDDINGS_DIR = _V2 / "knowledge" / "embeddings"

# (query, filter) — a spread across intents, categories, languages, and profile filters
QUERIES: list[tuple[str, Filter]] = [
    ("access control policy", Filter()),
    ("information security risk assessment", Filter()),
    ("incident response and management", Filter()),
    ("supplier and third party relationships", Filter()),
    ("business continuity management", Filter()),
    ("data protection and privacy", Filter()),
    ("encryption of information", Filter()),
    ("segregation of duties", Filter()),
    ("management review of the ISMS", Filter()),
    ("acceptable use of information assets", Filter()),
    ("threat intelligence", Filter()),
    ("logging and monitoring", Filter()),
    ("vulnerability management", Filter()),
    ("secure development lifecycle", Filter()),
    ("physical security controls", Filter()),
    ("human resource security awareness", Filter()),
    ("supplier information security agreements", Filter()),
    ("cloud security responsibilities", Filter()),
    ("network security controls", Filter()),
    ("backup and recovery", Filter()),
    ("risk treatment plan", Filter(document_profiles=("iso_standard",))),
    ("access control", Filter(categories=("ISO",))),
    ("control implementation guidance", Filter(document_profiles=("control_framework",))),
    ("NIST cybersecurity framework functions", Filter(categories=("NIST",))),
    ("governance and oversight responsibilities", Filter()),
    ("internal audit requirements", Filter()),
    ("code of conduct and ethics", Filter()),
    ("whistleblowing and reporting misconduct", Filter()),
    ("anti bribery and corruption", Filter()),
    ("vendor management best practices", Filter()),
    ("personal data breach notification", Filter()),
    ("consent for processing personal data", Filter()),
    ("data subject rights", Filter()),
    ("records of processing activities", Filter()),
    ("penalties for non compliance", Filter()),
    ("obligations of the data controller", Filter()),
    ("board responsibilities for governance", Filter()),
    ("financial disclosure requirements", Filter()),
    ("conflict of interest", Filter()),
    ("operational technology security controls", Filter()),
    # Arabic
    ("سياسة التحكم في الوصول", Filter()),
    ("تقييم مخاطر أمن المعلومات", Filter()),
    ("حماية البيانات الشخصية", Filter()),
    ("الضوابط الأساسية للأمن السيبراني", Filter(categories=("Saudi Regulations",))),
    ("التزامات مسؤول البيانات", Filter()),
    ("إدارة استمرارية الأعمال", Filter()),
    ("الحوكمة والرقابة الداخلية", Filter()),
    ("تشفير المعلومات", Filter()),
    ("إدارة الحوادث الأمنية", Filter()),
    ("متطلبات التدقيق الداخلي", Filter()),
]


def main() -> int:
    print("Loading corpus + providers from generated artifacts…")
    t = time.perf_counter()
    corpus = InMemoryCorpus.load(CHUNKS_DIR)
    keyword = InMemoryKeywordProvider(corpus)
    vector = InMemoryVectorProvider.load(corpus, EMBEDDINGS_DIR)
    print(f"  {len(corpus.chunks):,} chunks · vector matrix {vector._matrix.shape} · loaded in {time.perf_counter() - t:.1f}s\n")

    engine = RetrievalEngine(vector, keyword)
    print(f"{len(QUERIES)} queries against the real 117-document corpus\n" + "=" * 100)

    for i, (query, flt) in enumerate(QUERIES, start=1):
        ctx = engine.retrieve(RetrievalQuery(text=query, filter=flt, top_k=3))
        flt_note = "" if flt.is_empty() else f"   [filter: {', '.join(flt.document_profiles + flt.categories)}]"
        print(f"\n{i:>2}. {query}{flt_note}")
        if not ctx.results:
            print(f"     (no citable results — {'; '.join(ctx.warnings)})")
            continue
        for r in ctx.results:
            snippet = " ".join(r.text.split())[:70]
            print(f"     • {r.citation.formatted}")
            print(f"       conf={r.confidence:<6} profile={r.document_profile or '-':16s} “{snippet}…”")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
