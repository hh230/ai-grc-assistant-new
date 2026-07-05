# grc-regulatory-crawlers

The Regulatory Intelligence ingestion layer (Policy Intelligence PI-P2, ADR-0019): discovers
and fetches regulatory documents, detects changes against what is already stored, and feeds
new/updated documents through `grc_regulatory_intelligence`'s pure engine into storage.

```
RegulatorySourceRegistry (config, grc_regulatory_intelligence)
  -> HttpRegulatoryCrawler.discover(source)   -- HTML link discovery
  -> HttpRegulatoryCrawler.fetch(source, ref) -- HTML/PDF/text -> RegulatoryDocumentInput
  -> detect_change(previous_hash, current_hash)
  -> RegulatoryIntelligenceEngine.run(raw_document)  -- split + classify (PI-P1)
  -> RawDocumentStore / ObligationStore (structural ports; grc_persistence_web satisfies them)
```

- `http_fetcher.py` — `HttpFetcher`, the one seam real network I/O crosses (so everything
  above it is testable with a fake, never a real HTTP server). `UrllibHttpFetcher` is the
  stdlib-only concrete implementation.
- `robots.py` — `RobotsChecker`: robots.txt compliance, per-origin cached.
- `rate_limiter.py` — `PoliteRateLimiter`: a minimum delay between requests to the same host.
- `html_extraction.py` — stdlib `html.parser`-based link discovery and tag-stripping.
- `pdf_extraction.py` — `pypdf`-based text extraction (the one third-party dependency here).
- `crawler.py` — `HttpRegulatoryCrawler`: the reference `CrawlerPort` adapter composing all of
  the above. Identifies itself with a descriptive User-Agent; never bypasses robots.txt or the
  rate limiter.
- `observability.py` — `CrawlObserver` (crawl started/completed, documents found/changed,
  fetch/extraction/classification failures), with a `LoggingCrawlObserver` default and an
  `InMemoryCrawlObserver` test double.
- `runner.py` — `RegulatoryCrawlerRunner`: loads enabled sources, runs the crawler over each,
  and persists new/updated documents. Depends on `RawDocumentStore`/`ObligationStore`
  **structural protocols** (not a concrete DB import) — `grc_persistence_web`'s
  `RegulatoryRawDocumentRepository`/`RegulatoryObligationRepository` satisfy them by shape
  alone, so this package never depends on a database library.

**Politeness by construction:** every fetch passes through `RobotsChecker` and
`PoliteRateLimiter` first; there is no path that bypasses either. A failure fetching, parsing,
or classifying one document is observed and skipped — it never aborts the rest of a source's
crawl, nor another source's.

**Not in this package:** scheduling (no cron/`apps/worker` wiring yet), a review UI, or Policy
Hunter matching — see ADR-0019 for what is explicitly deferred.
