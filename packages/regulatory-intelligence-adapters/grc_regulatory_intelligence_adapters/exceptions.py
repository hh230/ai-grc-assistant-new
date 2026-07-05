"""Exceptions raised by the concrete Regulatory Intelligence adapters."""

from __future__ import annotations


class ConnectorFetchError(Exception):
    """A `RegulatoryConnectorPort` adapter could not fetch a source."""


class ClassificationRejectedError(Exception):
    """The classifier Tool's LLM output was malformed or classified into an unsupported
    category. Raised from `ClassifyRegulatoryObligationTool.run` so the Tool Registry
    records the invocation as `failed` before the error propagates (CLAUDE.md §19); the
    `LlmObligationClassifier` port adapter translates this into
    `grc_regulatory_intelligence.ObligationClassificationError` for the engine.
    """
