"""grc_regulation_ingestion_adapters — real I/O for the Saudi Regulations Ingestion Pipeline
(Knowledge Intelligence KI-P6, ADR-0030): the Google Drive index-catalog extractor, the
deterministic Board of Experts (laws.boe.gov.sa) page fetcher/parser, and the fetch/parse/store
orchestration runner. See README.md.
"""

from __future__ import annotations

from .boe_fetcher import BoeRegulationPageFetcher, FetchedRegulationPage
from .boe_parser import ParsedRegulation, ParsedSection, parse_boe_page
from .drive_catalog import DriveIndexCatalogSource, parse_regulation_index
from .runner import RegulationGapRunner, RegulationIngestionOutcome, short_code_for

__all__ = [
    "BoeRegulationPageFetcher",
    "FetchedRegulationPage",
    "ParsedRegulation",
    "ParsedSection",
    "parse_boe_page",
    "DriveIndexCatalogSource",
    "parse_regulation_index",
    "RegulationGapRunner",
    "RegulationIngestionOutcome",
    "short_code_for",
]
