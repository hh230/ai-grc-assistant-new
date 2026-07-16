# knowledge-importer (V2)

The Rasheed V2 Knowledge Import Pipeline:

1. **Discovery** — recursively scans a Knowledge Library root, detects supported
   document types (`.pdf`, `.docx`, `.xlsx`, `.txt`, `.md`), and writes one JSON
   manifest per document plus a combined `index.json`.
2. **Parsing** — extracts readable text from each discovered document (format-specific
   parser, reading order preserved, page boundaries preserved where the format has a
   notion of pages) and writes it to `v2/knowledge/imports/{document_id}.txt`.
3. **Profile assignment + Chunking** — assigns each document a Document Profile
   (`v2/knowledge/profiles/document_profiles.json`), segments its extracted text into a
   structure-preserving, parent/child chunk tree via the profile's Recognizer, and
   writes it to `v2/knowledge/chunks/{document_id}.json`.
4. **Embedding** — generates one vector per chunk via a pluggable provider, preserving
   all chunk metadata + citation, and writes `v2/knowledge/embeddings/{document_id}.json`
   plus a run manifest. Runs as a **separate phase** (it needs a provider, and a real
   vendor needs credentials) — see "Embedding phase" below.

The parse/chunk pipeline does **not** embed or retrieve anything. Chunk `text` is never
rewritten, summarized, translated, merged, or simplified — only whitespace-normalized
(see `chunking/text_utils.py`). Retrieval / semantic search / RAG / AI answers are later
phases, not implemented here.

The Knowledge Library itself is the single source of truth and lives **outside** this
repository (nothing here moves, renames, modifies, or copies the original files). The
library root is always an explicit runtime argument — see `config.py` for the default
development path and `--library-dir` below to override it. `v2/knowledge/library/` is
kept only as a placeholder; nothing depends on it.

Fully isolated inside `/v2`: standalone `uv` project, its own `.venv`/`uv.lock`, not a
member of the repository's root `uv` workspace. Runtime dependencies (`pypdf`,
`pypdfium2`, `python-docx`, `openpyxl`, `cryptography`) are scoped to this package only — chunking
itself adds no new dependencies (pure standard library).

## Usage

```bash
cd v2/packages/knowledge-importer
uv sync
uv run python -m knowledge_importer.cli
```

Optional overrides:

```bash
uv run python -m knowledge_importer.cli \
  --library-dir <path> \
  --manifests-dir <path> \
  --imports-dir <path> \
  --chunks-dir <path> \
  --profiles-catalog <path>
```

## Embedding phase

Embedding is deliberately a separate command, because it needs a provider (and a real
vendor needs credentials) — the parse/chunk pipeline above stays credential-free.

```bash
uv run python -m knowledge_importer.embedding.cli
```

It reads every chunked document from the index, embeds each chunk, and writes
`v2/knowledge/embeddings/{document_id}.json` (one record per chunk), a `_checkpoint.json`,
and `embedding_manifest.json` (the run summary).

**Provider is environment-driven — no vendor lock-in, no hardcoded keys.** Defaults to a
local, deterministic, dependency-free provider so the phase runs end-to-end with no
credentials or cost. Switch to a real vendor purely via environment:

```bash
EMBEDDING_PROVIDER=openai EMBEDDING_MODEL=text-embedding-3-large \
OPENAI_API_KEY=sk-… \
uv run python -m knowledge_importer.embedding.cli
```

Other tunables (all optional): `EMBEDDING_DIMENSION`, `EMBEDDING_BATCH_SIZE`,
`EMBEDDING_MAX_RETRIES`, `EMBEDDING_RETRY_BASE_DELAY`, `EMBEDDING_VERSION`. The API key is
read by the provider from the environment at call time — never stored in config, a
manifest, or an embedding record.

- **Provider interface** (`embedding/providers/`): a one-method `EmbeddingProvider`
  protocol. `local.py` (deterministic, offline — the default; also the slot for a future
  BGE/Nomic/Ollama local model) and `openai_provider.py` (stdlib `urllib`, injectable
  transport for testing) ship today. Adding Voyage/Gemini/etc. is one module + one line in
  `providers/registry.py`; the engine only ever sees the protocol.
- **Skip / regenerate:** an existing embedding is reused unless the chunk checksum
  changed, the model changed, or the embedding version changed. This makes every run
  idempotent — and is exactly what lets an interrupted run **resume automatically**:
  rerunning re-embeds only what's missing or stale. `_checkpoint.json` is a fast-path on
  top of that.
- **Batching + retry:** chunks are embedded in batches (`EMBEDDING_BATCH_SIZE`); each
  batch call is retried with exponential backoff. A batch that exhausts its retries
  records per-chunk failures and the run continues — one failure never halts the phase.
- **Lossless:** every embedding record is a superset of its chunk's metadata (all
  required citation/structure fields promoted to the top level, plus the complete chunk
  metadata block carried verbatim) — the raw chunk `text` body is the only thing not
  duplicated (it stays authoritative in `chunks/`, re-linkable by `chunk_id` + verifiable
  by `chunk_checksum`).

The local provider's vectors are structurally valid (correct dimension, L2-normalized,
deterministic) but **not** semantically meaningful — they exist to validate the engine
end-to-end without cost or data egress. Real semantic vectors come from swapping the
provider (above); retrieval that consumes them is a later phase.

## Tests

```bash
uv run pytest
```

## Architecture

- `discovery.py` — walks the library root, filters to supported extensions, derives
  each file's `category` from its top-level folder.
- `models.py` — `DocumentManifest`, the immutable record a document accumulates as it
  passes through pipeline stages.
- `parsers/` — one module per format (`pdf_parser.py`, `docx_parser.py`,
  `excel_parser.py`, `text_parser.py`, `markdown_parser.py`), each implementing the
  `Parser` protocol (`base.py`). `registry.py` maps extension → parser. A future format
  (or OCR for scanned PDFs) is added as one more parser module + one more registry
  entry — nothing else changes.
- `stages.py` — `PipelineStage` protocol + `IntakeStage` (file-system metadata) +
  `ParsingStage` (text extraction via the parser registry) + `ProfileAssignmentStage`
  (resolves each document's Document Profile) + `ChunkingStage` (segments the extracted
  text via the assigned profile's Recognizer). A failure at any stage is recorded on the
  manifest, never raised, so one bad document never stops the run. A future stage
  (embedding) is added by implementing the same protocol and appending it to the stage
  list in `pipeline.build_pipeline()` — no change to `pipeline.py` or `discovery.py`
  needed.
- `pipeline.py` — `KnowledgeImportPipeline`: discovers files, folds each one through the
  configured stages in order.
- `imports_store.py` — writes each document's extracted text to
  `imports_dir/{document_id}.txt`.
- `manifest_store.py` — writes each manifest to its own JSON file, writes the combined
  `index.json`, and prunes manifests for documents no longer present in the library.
- `chunks_store.py` — writes each document's chunks to
  `chunks_dir/{document_id}.json`; pruning of chunk files for removed documents runs
  once per CLI invocation.
- `chunking/` — the segmentation engine (see below).
- `cli.py` — entrypoint wiring the above together.

Re-running the importer over an unchanged library is idempotent: manifests, extracted
text, and chunks are overwritten with identical content (same `chunk_id`s, same
checksums), and manifests/chunk files for removed documents are deleted.

## Chunking architecture

Implements [`v2/docs/architecture/chunking-engine.md`](../../docs/architecture/chunking-engine.md)
(v1.1, with the Document Profile layer). Full design rationale lives there; this is the
code map:

- `chunking/profiles.py` — loads `v2/knowledge/profiles/document_profiles.json` (data,
  not code) and resolves a document's Document Profile: explicit override (highest
  priority) > `.xlsx` format override > category-level default > unmapped.
- `chunking/recognizers/` — one module per Recognizer (`standard_clause.py`,
  `regulation_article.py`, `contract_clause.py`, `policy_procedure.py`), each a pure
  boundary-detection function operating on page-tagged lines. `base.py` holds the
  shared `Boundary` type, the ToC dot-leader filter, and the density-based confidence
  score. `registry.py` maps a profile's `recognizer` name to its detector.
- `chunking/tabular.py` — sheet/row-group chunking for the `spreadsheet` profile;
  bypasses the generic tree assembler since its structure isn't leveled headings.
- `chunking/fallback_window.py` — sentence/paragraph-boundary-aware sliding window,
  used both for a whole document with no recognizable structure and for one
  structure-aware leaf that's too large to embed as a single chunk.
- `chunking/text_lines.py` — the generic engine: turns a flat `Boundary` list into a
  real parent/child tree (stack-based, level-driven), tracks page bounds from Phase 2's
  `\f` markers, and sub-windows any oversized leaf in place.
- `chunking/engine.py` — the Recognizer selection cascade: tries the assigned profile's
  recognizer, falls back through `standard_clause` → `policy_procedure` → whole-document
  windowing if confidence stays below threshold.
- `chunking/chunk_models.py` — the `Chunk` schema (architecture doc §9).
- `chunking/references.py` — detects (never resolves) candidate cross-reference
  mentions (`"see Clause 4.2"`, etc.).
- `chunking/text_utils.py` — `normalize_whitespace` (the *only* transformation ever
  applied to a chunk's text), Arabic-Indic digit normalization (matching only, never
  applied to stored text/code), language detection, slugify, sentence/paragraph break
  finding.

**Known limitation, found on the real corpus, disclosed honestly:** the numbered-clause
pattern (`standard_clause`, `contract_clause`) cannot always distinguish a genuine body
clause from a numbered footnote/endnote list, which is structurally identical after PDF
text extraction (`"59 See [NIST CSF], Section 2.3."` looks exactly like a numbered
clause). Observed once in `nist--nist sp 800-37...` producing an oversized "clause 59"
chunk that actually absorbed a run of footnotes. **No content is lost** — the footnote
text is fully present in the chunk, just structurally mislabeled — but the boundary
itself is imprecise. A targeted fix (detecting References/Notes/Endnotes sections, or
requiring higher local match density before accepting numbered lines as structural) is
a natural next refinement, not attempted here to avoid tuning against a single observed
case without broader validation data.

## Parsing notes

- **PDF** (`pdf_parser.py`) — a **backend chain**, not a single library. `PdfParser`
  tries each engine in `parsers/pdf_backends/` in order and the first to succeed wins:
  1. **pypdf** (`pypdf_backend.py`) — fast and correct for the large majority of the
     library. Requires `cryptography` (a runtime dependency) to decrypt AES-encrypted
     PDFs.
  2. **pypdfium2** (`pypdfium_backend.py`) — Chromium's PDF engine, more permissive;
     reads non-conformant-but-complete PDFs that pypdf rejects (e.g. files whose
     generator used newlines where the spec expects spaces, which trips pypdf's
     trailer/xref scanner). Only runs when pypdf raises.

  Every backend emits the same convention (one `\f` between pages, real `page_count`).
  The manifest records `parser_used` (the engine that produced the text), `parser_fallback`
  (true if a non-primary engine was used), `parser_attempts` (the ordered `{backend, ok,
  error}` trail), and — only when *every* backend fails — `failure_reason`. A new engine
  (a third library, or an OCR backend for scanned PDFs) is added by implementing the
  one-method `PdfBackend` protocol and appending it to `DEFAULT_PDF_BACKENDS` — nothing
  else in the parser, stage, or pipeline changes.
- **DOCX** (`docx_parser.py`, via `python-docx`) — walks the document body in document
  order so paragraphs and tables appear interleaved as in the source, not grouped
  separately. No reliable page concept, so `page_count` is always `None`.
- **XLSX** (`excel_parser.py`, via `openpyxl`) — sheet order, then row order, then
  column order; cells within a row are tab-separated. Sheets are the closest XLSX
  analogue of a page: separated by `\f`, `page_count` is the sheet count.
- **TXT / Markdown** (`text_parser.py` / `markdown_parser.py`) — read as-is; no page
  concept.
- When a parser exhausts every backend (corrupt file, unsupported internal format, etc.)
  the manifest gets `parsed: false`, `failure_reason` / `error` set to the joined backend
  errors, the full `parser_attempts` trail, and `status: "parse_failed"` — the pipeline
  continues with the next document.
