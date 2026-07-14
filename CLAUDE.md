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
- See `.claude/rules/` for style and testing conventions.
- `AGENTS.md` and `CLAUDE.md` are mirrored instruction files; every documentation change
  must update both, and `tests/test_instruction_docs.py` enforces exact synchronization.
- Before handing off work on an existing PR, inspect thread-aware unresolved review comments;
  flat conversation comments are not a complete review-status source.

## Multi-Agent Supervisor (Data Ingestion + Ratio Analysis)

`app.agents.supervisor_graph.run_supervisor_analysis(ticker)` is a real, working
implementation, wired to `GET /analysis/{ticker}/stream` (same SSE shape as
`/fundamentals/{ticker}/stream`). A `Command(goto=...)`-driven supervisor node makes an
LLM (`DEEPSEEK_MODEL_ROUTING`, must be `deepseek-chat` — see the DeepSeek structured-output
note below) routing decision each turn between two compiled-subgraph workers
(`data_ingestion`, `ratio_analysis`), with a hard invariant that overrides the LLM if it
tries to re-invoke a worker whose output already exists, or invoke `ratio_analysis` before
`financials` exists. State tracks which workers have run via an explicit `visited` list
field — not by parsing `messages` text — so control flow never depends on log wording.

**Requires a local Postgres** (new `postgres` service in `docker-compose.yml`, first
Postgres dependency this project has had) for `AsyncPostgresSaver` checkpointing — a
mid-run crash resumes from the last checkpoint instead of restarting `data_ingestion`.
`POSTGRES_URL` in `.env` points at `localhost:5433` for anything run directly on the host
(scripts, `pytest`, `uv run uvicorn` outside Docker); the `backend` container overrides it
via `docker-compose.yml`'s `environment:` block to the in-network `postgres:5432` hostname,
since containers can't reach each other via `localhost`. Verified live: interrupting a run
right after `data_ingestion` (`interrupt_after=["data_ingestion"]`) and resuming the same
`thread_id` correctly skips re-running `data_ingestion` and only invokes `ratio_analysis`.

**Module layout (SRP)**: `app/agents/supervisor_graph.py` owns *only* the graph/routing
logic — no Postgres, no lazy-init caching, no locks. It exposes
`init_supervisor_graph(checkpointer)` (compile + register the graph; must be called
exactly once) and `run_supervisor_analysis(...)` (asserts `init_supervisor_graph` was
already called — a clear error if not, rather than a confusing failure deep in graph
internals). Postgres connection lifecycle lives in `app/db.py`
(`open_pool(url)`/`close_pool(pool)`, no caching, no locking — just the two functions).
The actual startup/shutdown wiring is `app/core/lifespan.py`'s
`@asynccontextmanager lifespan(app)`: opens the pool, builds `AsyncPostgresSaver`, runs
`.setup()`, calls `init_supervisor_graph(checkpointer)` to inject it into the agent module
(push, not pull), and closes the pool in a `finally` on shutdown (even if `.setup()`
itself failed, so a broken startup never leaks the pool). `app/main.py` only wires
`FastAPI(lifespan=lifespan)` + CORS + `include_router(...)` for `app/routers/streaming.py`
(both SSE routes) and `app/routers/core.py` (the `/health`/`/chat` stubs) — no
Postgres/agent-specific code left in it at all. This replaced an earlier design where
`supervisor_graph.py` itself lazily built and cached the pool/checkpointer/graph behind an
`asyncio.Lock`, called eagerly from an inline lifespan in `main.py` — functionally
equivalent for fail-fast purposes, but mixed unrelated concerns into one module and one
file; the push-based injection pattern above (adapted from a sibling reference project,
`finance-ai-agent`) needs no lock at all, since there's no lazy path left to race on.
Verified live after the restructure: real ticker requests still work end-to-end through
the new module split, and with Postgres stopped, `docker compose up backend` still fails
outright after ~30s (`psycopg_pool.PoolTimeout: couldn't get a connection after 30.00 sec`
→ `ERROR: Application startup failed. Exiting.`) rather than starting and silently failing
requests later; recovers cleanly once Postgres is back.

**Fixed properly, not by hand-listing types**: LangGraph's checkpoint serializer used to
log `Deserializing unregistered type app.models.FinancialStatements from checkpoint. This
will be blocked in a future version` when checkpointing our custom Pydantic models via
msgpack — found via live verify-agent. This isn't just a cosmetic warning: it's the
non-strict side of a real security posture (`langgraph`/`langgraph-checkpoint` security
advisory GHSA-g48c-2wqr-h844 / CVE-2026-28277, unsafe msgpack deserialization; fixed
upstream in `langgraph-checkpoint>=...` with the `LANGGRAPH_STRICT_MSGPACK` mechanism —
we're on `langgraph==1.2.7`/`langgraph-checkpoint==4.1.1`, both well past the fix).

An earlier attempt at this fix manually constructed `JsonPlusSerializer(
allowed_msgpack_modules=[FinancialStatements, FundamentalRatios])` and passed it to
`AsyncPostgresSaver` — this "worked" (silenced the warning) but was a sidestep: a
hand-maintained list that would silently miss any new checkpointed Pydantic type (it
already missed `IncomeStatement`/`BalanceSheet`/`CashFlowStatement`, nested inside
`FinancialStatements`) and duplicated a mechanism the framework already provides.

**Actual fix**: set `LANGGRAPH_STRICT_MSGPACK=true` as a real OS env var before any
`langgraph` import in the process (`os.environ.setdefault(...)` at the very top of
`app/main.py`, and in `tests/conftest.py` for the test suite — it can't go through
`app/config.py`'s `Settings`/`.env`, since LangGraph reads it via `os.getenv` directly,
not through our own settings object, and pydantic-settings' `extra_forbidden` default
means adding it to `.env` without a matching `Settings` field crashes at startup). With
strict mode on, `StateGraph.compile(checkpointer=...)` (in `build_supervisor_graph`)
automatically walks the graph's own state schema (`SupervisorState`'s field types) and
calls `checkpointer.with_allowlist(...)` — no manual serde construction needed at all,
and it correctly picked up the nested statement types the manual list missed. Verified:
`build_supervisor_graph(InMemorySaver()).checkpointer.serde._allowed_msgpack_modules`
contains all five of our checkpointed model types automatically; live re-verified against
the real Postgres-backed container with zero warnings in the logs.

**Stale-container gotcha (verify-agent process note, not a code bug)**: this repo's
`docker compose` `backend` container runs `uvicorn` without `--reload` — the `./app:/app/app`
bind mount means file edits appear inside the container, but the running process doesn't
pick them up until the container restarts. A `backend` container left running from a much
earlier session silently served stale code (missing the new route entirely, 404s) while
looking otherwise healthy. `docker compose up -d --build backend` after backend code
changes, not just leaving an old container running, is required before verifying live.

## Analyst Team (News/Sentiment + Valuation + Report-Writer + Critic)

`app.agents.analyst_team_graph.run_team_analysis(ticker)` is a real, working
implementation, wired to `GET /report/{ticker}/stream` (same SSE shape as the other two
routes). Expands the 2-agent supervisor above into an analyst team: `Send`-based fan-out of
Data-Ingestion+Ratio-Analysis (the existing supervisor, reused unchanged as a black-box
branch) and News/Sentiment, converging into Valuation, Report-Writer, then Critic. **True 3-way
parallelism is impossible** — Ratio Analysis needs Data Ingestion's own output — so the
fan-out is 2-way (financials branch, news branch); Ratio Analysis runs sequentially inside
the financials branch, which is fine since it's pure/fast (no I/O). No LLM-driven routing
at the outer level (unlike the reused supervisor's own internal routing) — this pipeline's
shape is fully deterministic, so static `Send`/edges are used instead, confirmed with the
user rather than assumed.

**Guardrail placement**: ticker sanitization is enforced at API/agent/tool boundaries, while
final report output passes through deterministic guardrails between Report-Writer and Critic
before HITL. Keep numeric hallucination/PII/disclaimer checks there rather than scattering
LLM-specific checks through individual prompts; unsupported report figures become bounded
revision requests through the existing critic loop, then are deterministically redacted after
max revisions. This guarantee only holds when `ratios` is available — on a degraded
financials branch (`SourceUnavailableError`, `ratios=None`), both guardrail checks
intentionally no-op (nothing to validate numbers against), so a report on that path may still
contain unverified figures; this is accepted, tested behavior, not a gap.

**Checkpoint/trace nesting**: reusing the supervisor as a branch meant its
`run_supervisor_analysis` needed a way to avoid colliding with the outer graph's own
Postgres checkpoint thread (both defaulting to `thread_id=ticker` against the same shared
checkpointer would let a resume return the wrong graph's state) — fixed by adding an
optional `config: RunnableConfig | None` passthrough param: the outer graph calls
`run_supervisor_analysis(ticker, thread_id=f"{ticker}:financials", config=config)`,
overriding just the thread_id while preserving callbacks, so LangSmith nests the reused
subgraph's run under the outer team run instead of it appearing as an unrelated top-level
trace. Verified live via the LangSmith API (`Client.list_runs(trace_id=...)`): all ~30
spans of a real run share one `trace_id`, and `financials_branch`/`news_branch` start
within 166 microseconds of each other with genuinely overlapping time windows — real
concurrency, not just claimed.

**Sector benchmarks are always live-fetched, never hardcoded** (`app/services/
sector_benchmarks.py`): a small curated peer-ticker table per sector (just *which* tickers
to ask, e.g. Technology → MSFT/GOOGL/META/NVDA/ORCL) feeds live concurrent
`yfinance.Ticker(peer).info` calls (`trailingPE`/`priceToBook`/`returnOnEquity`), median
computed at request time. Peer fetches are `tenacity`-retried and run via `asyncio.gather`
so a 5-peer basket costs ~one network round-trip, not five sequential ones. `Valuation`'s
P/E, P/B, *and* ROE all come from this same live yfinance call — deliberately independent
of whether the financials branch (which has its own, unrelated `ratios.roe`) succeeded, so
Valuation still produces a real answer even when Data Ingestion fails entirely.

**Two real bugs found only by live verify-agent** (both invisible to unit tests, which
mock the LLM):

1. `news_sentiment_graph.py` and `report_writer_graph.py` both initially used
   `deepseek_model_generation` for their `with_structured_output` calls — but that setting
   is configured as a thinking model (`deepseek-v4-flash`) in the real `.env`, and
   DeepSeek's structured-output mode 400s on thinking models ("Thinking mode does not
   support this tool_choice" — the same constraint already documented below for the
   Filings RAG pipeline, re-discovered here). Fixed by switching both to
   `deepseek_model_routing` (already the project's designated non-thinking-model setting,
   previously only used by the supervisor's routing decision).
2. `AnalystReport.risk_factors`/`key_themes` (`list[str]`) crashed with a Pydantic
   `ValidationError` in 5 of 10 real ticker runs — DeepSeek's structured output sometimes
   returns a JSON-stringified array or a numbered/bulleted multiline string instead of a
   real list for these two fields. Fixed with a `field_validator(mode="before")` on both
   fields (`app/models.py`) that tolerates the common shapes (JSON-stringified list,
   numbered/bulleted multiline string, or a single plain sentence) rather than hard-failing
   the whole report after ~20s of prior agent work. `NewsSentimentResult` has a similar,
   rarer failure mode (the LLM occasionally omits every field but `ticker`) that's already
   handled by `news_sentiment_graph.py`'s existing degrade-to-neutral path, not a new bug.
3. The Critic Agent (`app/agents/report_critic_graph.py`) uses DeepSeek structured output
   with the same non-thinking routing model constraint as the other structured-output agents.
   Live verify found `Report-Writer` can still return `None` twice for a ticker; the direct
   `run_report_writer(...)` API raises clearly, and the analyst-team graph lets terminal
   report-writer failures propagate instead of substituting a meaningless fallback report.
   Latest 10-ticker critic eval (`uv run python scripts/evaluate_critic_loop.py`) measured
   average first-draft→final score improvement of **+0.19**, above the +0.10 gate; some
   tickers still hit `max_revisions_reached` and proceed with the best draft.
4. The verification script's own "sequential baseline" measurement was comparing unequal
   work (only timing 2 of the 5 agents against the full 5-agent parallel run), making its
   speedup number meaningless — fixed to run the same 5-agent total workload sequentially.
   Real, corrected result: **10/10 tickers passed, 19.0s average (well under the 120s
   budget), 1.11x speedup** — modest but genuine, bounded by how much slower the
   news branch (Tavily search + LLM scoring) is than the financials branch it overlaps with.

## DataIngestionAgent / RatioEngine

`app.agents.ingestion_graph.run_ingestion(ticker)` and `app.services.ratio_engine.RatioEngine`
are real, working implementations, wired to `GET /fundamentals/{ticker}/stream` (SSE:
`started` → `result`/`error` events). Without a configured `LANGSMITH_API_KEY`, fallback-chain
transitions log locally via the standard `logging` module (visible in
`docker compose logs backend` or stdout) instead of failing — that's the intended graceful
degradation, not a bug.

**SEC XBRL is now the accounting source of truth** (`edgartools/cache → direct SEC
Company Facts → yfinance`). `app.services.xbrl_cache` reuses the lifespan-managed Postgres
pool, creates `companies`/`filings`/`xbrl_facts` idempotently at startup, and refreshes on
demand after a one-hour TTL. It retains all standardized Company Facts history plus detailed
dimensions from the latest five 10-Ks and two 10-Qs; exact facts live in Postgres while filing
narrative embeddings remain in Weaviate. Bulk psycopg writes must use
`connection.cursor().executemany(...)`—`AsyncConnection` itself has no `executemany` method.
SEC downloads and EdgarTools parsing must finish before checking out the write connection;
keep the transaction limited to the advisory-lock recheck and atomic upserts so slow vendor
I/O cannot starve the Postgres pool.
For detailed 10-K/10-Q records, Edgar's `period_of_report` is authoritative; Company Facts can
contain comparative periods and later instant facts under the same accession, so an older
comparative fact must never overwrite filing metadata and a maximum fact date is not a safe
replacement for the filing's actual reporting period.

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
