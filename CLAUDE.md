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
