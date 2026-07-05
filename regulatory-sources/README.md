# Regulatory sources (as data)

Regulatory sources that the Regulatory Intelligence crawlers poll live here as **data, not
code** (CLAUDE.md §13's "frameworks are data" principle, applied to regulators — see
[ADR-0019](../docs/adr/0019-regulatory-connectors-and-crawlers.md)). Onboarding a new
regulator is a PR that adds one JSON file here — never a code change.

Loaded by `grc_regulatory_intelligence.source_config` into a `RegulatorySourceRegistry`; see
that module's docstring for the canonical schema. Layout: `<jurisdiction>/<source_id>.json`.

**Initial set (Saudi Arabia):** SAMA, CMA, NCA, SDAIA, MHRSD, ZATCA — see `sa/`.

Every source's `base_url` here is the regulator's public top-level domain. A crawler's
discovery step (`CrawlerPort.discover`) finds specific regulation/circular pages from that
root; this file does not hardcode deep links, since regulator site structures change and
verifying an exact sub-path isn't something a config file should assert without a live check.

`enabled: true` only means the source is a candidate for polling if/when something schedules
a crawl (`RegulatoryCrawlerRunner`) — no source is polled automatically by merely existing
here; there is no scheduled job wired up yet (PI-P2 stops at the runner/library level, per its
ADR).
