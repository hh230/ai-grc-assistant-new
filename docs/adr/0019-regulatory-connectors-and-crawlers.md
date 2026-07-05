# ADR 0019: Regulatory Connectors / Crawlers — source registry, polite web crawling, change
detection, and the crawler orchestrator

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §5, §13, §16, §17, §19, §20, §22; ADR 0007, 0017, 0018

## Context

Regulatory Intelligence PI-P1 (ADR-0018) built the pure split-then-classify engine and its
storage, but nothing yet discovers or fetches real regulatory content — every prior test fed
the engine a document constructed by hand. PI-P2 is the ingestion layer: given a set of
regulators to watch, find their published regulations/circulars, fetch them, detect whether
anything is new, and hand new/changed content to the PI-P1 engine.

This is the same "data, not code" problem the Framework Engine (ADR-0007) already solved for
compliance frameworks, applied to regulators: which regulators exist, where their content
lives, and how often to check should be configuration, not a `match regulator_name:` branch
buried in a crawler. Politeness (robots.txt, rate limits, identification) is a hard
requirement, not an optimization — this is a compliance product; it cannot itself behave like
an aggressive scraper against government infrastructure.

## Decision

We will:

1. Extend `packages/regulatory-intelligence` (still zero third-party dependencies) with:
   `RegulatorySource`/`SourceType`/`PollingFrequency`/`RegulatorySourceRegistry` (an in-memory
   catalog, mirroring `grc_framework_engine.FrameworkCatalog`'s role); `source_config.py`, a
   thin local-JSON loader in the same package (mirroring `grc_framework_engine.files`'s
   precedent — reading local, static config with only `json`/`pathlib` does not violate "no
   external dependencies," it is not network I/O); `RegulatoryDocumentInput`/
   `DiscoveredDocumentRef`/`DocumentContentType` (crawler output value objects, with
   `RegulatoryDocumentInput.to_raw_regulatory_document()` as the anti-corruption translation
   into PI-P1's `RawRegulatoryDocument`, CLAUDE.md §15); `change_detection.py`
   (`DocumentChangeType`, pure `detect_change`, keyed on content hash — URL is compared
   directly as the storage lookup key, not separately hashed); and `CrawlerPort` (discover one
   source's candidate documents, then fetch/normalize one).
2. Add `/regulatory-sources/<jurisdiction>/<source_id>.json` — configuration, not code — with
   the initial Saudi set: SAMA, CMA, NCA, SDAIA, MHRSD, ZATCA, each a `website` source polled
   `weekly`. Every `base_url` is the regulator's public top-level domain only; this file does
   not assert a specific deep-linked listing page, since verifying an exact sub-path isn't
   something a config file should claim without a live check.
3. Add `packages/regulatory-crawlers` (depends on the engine + `pypdf`, the one third-party
   dependency this phase adds): `HttpFetcher`, a one-method seam all network I/O crosses
   (`UrllibHttpFetcher` is the only concrete implementation — stdlib `urllib`, no new HTTP
   library) so every other module is testable against a fake transport, never a real server;
   `RobotsChecker` (robots.txt via `urllib.robotparser`, per-origin cached, default-allow when
   unreachable); `PoliteRateLimiter` (a minimum per-host delay); `html_extraction.py` (stdlib
   `html.parser`-based link discovery and tag stripping — no new HTML library);
   `pdf_extraction.py` (`pypdf`-based text extraction, raising on unreadable or textless
   PDFs); `HttpRegulatoryCrawler` (`CrawlerPort`, composing all of the above — every fetch
   passes through robots.txt and the rate limiter, unconditionally); `observability.py`
   (`CrawlObserver`: crawl started/completed, documents found/changed,
   fetch/extraction/classification failures — `LoggingCrawlObserver` default,
   `InMemoryCrawlObserver` test double); and `RegulatoryCrawlerRunner`, the orchestrator that
   loads enabled sources, runs the crawler, detects changes, and feeds new/updated documents
   through the PI-P1 engine into storage.
4. Keep `RegulatoryCrawlerRunner` decoupled from any concrete database: its
   `RawDocumentStore`/`ObligationStore` dependencies are **structural `Protocol`s**, not
   imports of `grc_persistence_web`. `grc_persistence_web.RegulatoryRawDocumentRepository`/
   `RegulatoryObligationRepository` satisfy them by method signature alone — this package
   never depends on a DB driver.
5. Extend `RegulatoryRawDocumentRepository` (`packages/persistence-web`) with
   `get_latest_content_hash(source_id, url)` and `list_latest_urls_by_source(source_id)` —
   the two read queries change detection needs — plus a supporting index
   (`apps/web/lib/db/migrations/0017_regulatory_documents_url_index.sql`). No new tables:
   PI-P1's schema already models "each version of a document is its own immutable row."
6. Every document is processed fail-safe (CLAUDE.md §16): a fetch, extraction, or
   classification failure for one document is observed and skipped, never aborting the rest
   of a source's crawl or another source's. Removed/unavailable documents are detected
   (a previously-stored URL no longer discovered) and reported via observability only — no
   schema change to soft-delete or flag them, since nothing yet consumes that state.
7. Explicitly out of scope for this phase: any scheduling (`apps/worker`/cron wiring), a
   review UI, `apps/api` wiring, and Policy Hunter matching. All obligations produced by this
   pipeline remain `pending_review`, per PI-P1's human-in-the-loop default — this phase adds
   volume to that queue, not a new way to bypass it.

## Consequences

**Positive**
- Onboarding a seventh regulator, or a new jurisdiction entirely, is a JSON file — no code
  change, matching the Framework Engine's precedent for the same class of problem.
- The one seam that touches the network (`HttpFetcher`) is small enough that every other
  module (robots, rate limiting, HTML/PDF normalization, the crawler, the runner) has full,
  deterministic test coverage against a fake transport — 27 tests in
  `packages/regulatory-crawlers` alone, none touching a real server.
- `RegulatoryCrawlerRunner`'s structural-protocol dependency on storage means
  `packages/regulatory-crawlers` has exactly one third-party dependency (`pypdf`) and no
  database driver at all, keeping it honestly a crawling library, not a persistence layer.
- Politeness is structural, not a convention to remember: there is no code path in
  `HttpRegulatoryCrawler` that fetches a URL without first checking robots.txt and waiting on
  the rate limiter.

**Negative / costs**
- `HttpRegulatoryCrawler`'s discovery heuristic (collect every `<a href>` on `base_url`) is
  necessarily generic — it does not know a given regulator's site structure and will surface
  irrelevant links (navigation, social media, etc.) alongside real regulation pages. Refining
  per-source discovery (e.g. a listing-page path, or pagination) is future work, added as
  source configuration or a source-specific `CrawlerPort` variant, not a rewrite of this one.
- No OCR: a scanned, image-only PDF (no embedded text layer) raises `CrawlerFetchError` and
  is reported as a fetch failure. Some regulator publications are scanned; those are not
  ingested until an OCR adapter is added behind the same `pdf_extraction` seam.
- The `regulatory-sources/*.json` `base_url`s are each regulator's root domain, not a
  verified listing-page URL — a real crawl run's discovery quality depends on that root
  actually linking to regulation content near the top level, which was not verified against
  the live sites in this phase (no browsing was performed to confirm).
- Nothing schedules a crawl yet; `RegulatoryCrawlerRunner` is a library other code must call.

## Alternatives considered

- **Have `RegulatoryDocumentInput` carry raw bytes and a `content_type`, extracting text
  inside the pure engine.** Rejected: extraction of bytes-to-text needs a PDF/HTML parsing
  library, which would violate `grc_regulatory_intelligence`'s "no external dependencies"
  rule (ADR-0018). Normalization to plain text is the crawler adapter's job; the engine only
  ever sees text.
- **Depend on `grc_persistence_web` directly from `packages/regulatory-crawlers`.** Rejected:
  would make a crawling library depend on a Postgres-specific adapter package for no benefit
  over a structural `Protocol` — anyone can satisfy `RawDocumentStore`/`ObligationStore`
  (an in-memory store for a script, a different database entirely) without this package
  changing.
- **Add `beautifulsoup4`/`lxml` for HTML parsing.** Rejected for this phase: the discovery/
  normalization needs (find `<a href>`, strip tags) are fully served by the standard
  library's `html.parser`; adding a dependency for functionality already available was not
  justified. `pypdf` was added because there is no stdlib PDF parser at all.
- **Wire a scheduled job (`apps/worker`) in this phase.** Rejected per explicit scope: this
  ADR builds the library the future job will call; standing up the schedule itself is a
  separate, later decision (also needs operational concerns — concurrency across sources,
  observability sink choice — not yet decided).
