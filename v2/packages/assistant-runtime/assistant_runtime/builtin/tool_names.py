"""The registry names of the real tools that built-in capabilities route their steps to (ADR 0048).

A Capability names a tool by these **strings only** — it never imports a tool package (the
capability layer stays free of tool dependencies; tools are reached through the registry, CLAUDE.md
§9/§10). The composition root (`grc-assistant`) registers each real tool under exactly the matching
name, and its test guards these constants against the real tools' names, so this module is the
**single source** of the capability→tool contract and a rename cannot silently break routing.
"""

from __future__ import annotations

# Grounded RAG (retrieve → generate → validate → cited answer). == pipeline_tool.RUN_PIPELINE_TOOL
RUN_PIPELINE_TOOL = "run_pipeline"
# Deterministic control-catalog lookup.            == framework_library.CONTROL_LIBRARY_TOOL
CONTROL_LIBRARY_TOOL = "framework_control_library"
# Raw (uncited) generation, for pure drafting.     == llm_tools.GENERATE_TEXT_TOOL
GENERATE_TEXT_TOOL = "generate_text"
# Lexical / semantic / hybrid search.              == search_tools.{LOCAL,VECTOR,HYBRID}_SEARCH_TOOL
LOCAL_SEARCH_TOOL = "local_search"
VECTOR_SEARCH_TOOL = "vector_search"
HYBRID_SEARCH_TOOL = "hybrid_search"
# Document text extraction.                         == document_tools.READ_{PDF,DOCX,EXCEL}_TOOL
READ_PDF_TOOL = "read_pdf"
READ_DOCX_TOOL = "read_docx"
READ_EXCEL_TOOL = "read_excel"
