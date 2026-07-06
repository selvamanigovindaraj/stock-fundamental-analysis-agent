# Stock Fundamental Analyser

Multi-agent stock fundamental analysis agent.

## Stack

- Backend: FastAPI + LangGraph + LangChain, Python 3.12, `uv`
- Vector store: Weaviate Cloud (no local vector DB service)
- LLM: DeepSeek (`deepseek-chat`), accessed via the OpenAI-compatible API at `https://api.deepseek.com`
- Web search: Tavily
- Frontend: React 19 + Vite + TypeScript + Tailwind CSS

## Run

```
cp .env.example .env   # fill in API keys + Weaviate Cloud URL/key
docker compose up --build
```

Backend: http://localhost:8001
Frontend: http://localhost:5174

(Host ports are remapped from the containers' defaults of 8000/5173 in `docker-compose.yml` to avoid clashing with other projects' containers on this machine — adjust back if you don't have that conflict.)

## Conventions

- Backend imports use the `app.*` prefix; run uvicorn from the project root (`uvicorn app.main:app`).
- Everything is currently a stub (`raise NotImplementedError` / `pass`) — see `.claude/rules/` for style and testing conventions.

## DataIngestionAgent / RatioEngine

`app.agents.ingestion_graph.run_ingestion(ticker)` and `app.services.ratio_engine.RatioEngine`
are real, working implementations, wired to `GET /fundamentals/{ticker}/stream` (SSE:
`started` → `result`/`error` events). Without a configured `LANGSMITH_API_KEY`, fallback-chain
transitions log locally via the standard `logging` module (visible in
`docker compose logs backend` or stdout) instead of failing — that's the intended graceful
degradation, not a bug.

**Banks/financial institutions (e.g. JPM) are now supported.** Their GAAP statements have no
Cost of Revenue/Gross Profit/Operating Income concept (net interest income model instead) and
no classified current/non-current balance sheet — these fields come back as `math.nan` (not
`0.0`) in `IncomeStatement`/`BalanceSheet`, so `gross_margin`/`operating_margin`/
`interest_coverage`/`current_ratio`/`quick_ratio`/`operating_cash_flow_ratio` correctly read as
NaN ("not applicable") rather than a misleading `0%`/`0.0`. `debt_to_equity`, `net_margin`,
`roe`, `roa`, `asset_turnover`, and `free_cash_flow` remain real numbers for banks. This is a
deliberate two-tier sentinel convention in the 3 adapters (`app/services/financial_sources/*`):
fields that are a genuine zero when absent (e.g. `Inventory` for services companies like META)
default to `0.0`; fields that are structurally inapplicable for a whole sector default to
`math.nan`. Don't collapse this back to a single default — it's load-bearing (see the adapter
docstrings/comments for exactly which fields are which).

**Known caveat**: relaxing these fields to optional applies to *all* tickers, not just banks —
a transient data glitch on e.g. `Gross Profit` for a normal company at the yfinance tier will
now "succeed" with `gross_margin=NaN` instead of falling through to edgartools/SEC EDGAR like
other missing fields still do. Accepted tradeoff (no cheap way to detect "this ticker is a
bank" short of a sector/SIC lookup, which would be over-engineering for this); exposure is
narrow since `Total Revenue`/`Total Assets`/`Total Liabilities`/`Stockholders Equity` etc. stay
required and still trigger the full fallback chain on failure.

**Also fixed**: `edgartools`'s `standard_concept == "Revenue"` normalization silently maps to
the wrong (much narrower) tag for banks — e.g. JPM's `PrincipalTransactionsRevenue` (~$27B)
instead of true total revenue (~$182B), which inflated `net_margin` past 100%. Only caught by
live-verifying against real JPM data, not by unit tests against synthetic fixtures.
`edgartools_source.py`'s `_find_total_revenue` now tries the raw `RevenuesNetOfInterestExpense`/
`Revenues` concepts first before falling back to `standard_concept`.

## Filings RAG pipeline

`app.services.filings.ingest.ingest_ticker_filings(ticker)` (download via `edgartools` →
extract MD&A/Risk Factors → chunk → embed via Voyage → store in Weaviate, collection name
`weaviate_filings_collection`) and `app.agents.filings_rag_graph.answer_filing_question(question,
ticker)` (retrieve → `grade_documents` → generate, with citations) are real, working
implementations, wired as a tool at `app/agents/tools/filings_rag_tool.py`. Verified live
end-to-end against real AAPL filings, Voyage, Weaviate Cloud, and DeepSeek — including
idempotent re-ingestion (re-running for the same filing overwrites its chunks in place via a
deterministic UUID, doesn't duplicate).

**`grade_documents` uses Voyage's reranker (`rerank-2.5`), not an LLM classifier.** Originally
built with a DeepSeek structured-output binary classifier (see the now-removed
`deepseek_model_structured` setting), swapped to `voyageai.AsyncClient.rerank` per explicit
request — one purpose-built reranking call instead of a structured-output round-trip.
`_RELEVANCE_THRESHOLD = 0.5` in `filings_rag_graph.py` is a judgment call, not derived from any
published Voyage cutoff (verified live: relevant chunks scored ~0.6-0.75, irrelevant ~0.3 for a
typical query) — tune if false-positive/negative rates matter in practice.

**Voyage AI free tier is extremely restrictive**: without a payment method on the account, it's
capped at 3 requests/minute and 10K tokens/minute — a single-ticker ingestion (4 filings, ~275
chunks) blows through this in one batched embed call and fails even after 3 retries. This isn't
a code bug (the retry-then-abort-cleanly design is working as intended — no partial writes on
failure); it's an account-tier limitation. A payment method has since been added and full-scale
ingestion for AAPL (275 chunks, one batched embed call) is confirmed working, taking ~100s.

**SEC-rendered filing text has recurring page-footer noise embedded inline** (e.g.
`"Apple Inc. | 2025 Form 10-K | 21"`) — found live via a RAGAS eval run where a real question
about tariffs got zero retrieved citations despite the content being correctly ingested
(confirmed via a Weaviate BM25 keyword search). Root cause: the footer created a near-empty
chunk (just a section header + page number) that ranked ahead of the real content in semantic
search for that query. `chunker.py`'s `_PAGE_FOOTER_RE` now strips this pattern before
chunking. Re-running the 5-pair eval after the fix showed context_recall improve (0.60 → 0.70)
and faithfulness dip slightly (0.73 → 0.69) — expected noise at n=5, not a signal to keep
tuning retrieval against; don't over-index on single-example RAGAS deltas at this sample size.

**Known limitation**: re-ingestion overwrites chunks by deterministic `(ticker, accession_no,
section, chunk_index)` id, but doesn't delete chunks whose index no longer exists if a
section's chunk count *shrinks* between runs (e.g., from a future chunking-logic change) —
those would become orphaned stale entries. Not currently exercised (chunk counts have stayed
stable across re-ingestions so far); would need an explicit delete-then-reinsert-per-section
step if this becomes a real scenario.

**DeepSeek's structured-output (`with_structured_output`) requires `method="function_calling"`
and a non-thinking model** — verified live: the default strict JSON-schema mode 400s
("This response_format type is unavailable now"), and forced tool-choice 400s against a
thinking-mode model ("Thinking mode does not support this tool_choice"). No longer load-bearing
for `grade_documents` (now Voyage rerank, not an LLM classifier — see above), but still true of
DeepSeek generally and worth knowing if structured output is needed elsewhere later.

**RAGAS 0.4.3 has a real import bug**: it unconditionally imports
`langchain_community.chat_models.vertexai.ChatVertexAI`, which doesn't exist in any
`langchain-community` release compatible with this project's `langchain>=1.0`. Pinning
`langchain-community` to an old pre-1.0 release (to keep that shim) creates an unsatisfiable
resolver conflict with `langgraph`/`langchain-openai` already in main deps — don't try that
again. `scripts/evaluate_filings_rag.py` instead stubs the missing submodule into
`sys.modules` before importing `ragas` (we never use VertexAI). `ragas`/`langchain-community`
live in the `eval` optional-dependency group (`make eval-filings-rag`), never in main deps.

**Known gap**: `tests/fixtures/filings_qa.json` has 5 real, hand-verified Q&A pairs (not 30) —
the 30-pair/faithfulness-≥0.85/context-recall-≥0.80 acceptance gate from the original spec is
**not met**. This is a content-curation task (sourcing and fact-checking 25 more real filing
Q&A pairs), not a coding gap — the harness (`make eval-filings-rag`) is complete and will pick
up more pairs added to the fixture file automatically.
