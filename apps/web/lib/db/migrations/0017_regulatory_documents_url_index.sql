-- Regulatory Connectors / Crawlers (PI-P2, ADR-0019): supports the crawler runner's
-- change-detection query (latest known content_hash for one source+url) and the
-- removed/unavailable-document scan (every URL previously seen for one source). Each new
-- version of a document is its own immutable row (content_hash is unique per 0016), so
-- "latest by URL" requires ordering by created_at, not just an equality lookup.
CREATE INDEX IF NOT EXISTS regulatory_raw_documents_source_url_idx
  ON regulatory_raw_documents (source_id, url, created_at DESC);
