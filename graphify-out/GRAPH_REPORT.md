# Graph Report - stock-fundamental-analyser  (2026-07-15)

## Corpus Check
- 133 files · ~36,370 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1023 nodes · 2417 edges · 65 communities (56 shown, 9 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 187 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ddbbb9ab`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Financial Data Sources
- News and Report Models
- Supervisor Orchestration
- Report Writer Graph
- Streaming Supervisor API
- Analyst Team Pipeline
- Valuation Analysis
- Filing Ingestion
- XBRL Cache
- React Analysis UI
- Frontend Dependencies
- News Sentiment Graph
- Team Analysis Tests
- Weaviate Retrieval Tests
- Ingestion Fallback Graph
- Financial Models
- TypeScript Configuration
- Adaptive Query Router
- Vector Search Tooling
- Shared Test Fixtures
- Ratio Engine
- Ratio Analysis Graph
- Ingestion Tests
- Lifespan Tests
- Project Architecture Docs
- Conversation Memory
- Semantic Response Cache
- Token Cost Tracking
- Prompt Registry
- Container Services
- Quality Gates
- User Feedback
- Input Guardrails
- Output Safety Filter
- Cache Placeholder Tests
- Retrieval Placeholder Tests
- Routing Placeholder Tests
- Code Style
- Frontend Source

## God Nodes (most connected - your core abstractions)
1. `FinancialStatements` - 58 edges
2. `SourceUnavailableError` - 50 edges
3. `Document` - 44 edges
4. `sanitize_ticker()` - 41 edges
5. `get_settings()` - 40 edges
6. `AnalystReport` - 31 edges
7. `NewsSentimentResult` - 29 edges
8. `ValuationResult` - 28 edges
9. `WeaviateRetriever` - 27 edges
10. `FundamentalRatios` - 26 edges

## Surprising Connections (you probably didn't know these)
- `Stock Fundamental Analyser` --semantically_similar_to--> `Stock Fundamental Analyser`  [INFERRED] [semantically similar]
  CLAUDE.md → AGENTS.md
- `Pull Request Verification Checklist` --semantically_similar_to--> `Testing Conventions`  [INFERRED] [semantically similar]
  .github/pull_request_template.md → .claude/rules/testing.md
- `_FakeCompiledTeamGraph` --uses--> `FinancialStatements`  [INFERRED]
  tests/agents/test_analyst_team_graph.py → app/models.py
- `_FakeRoutingLLM` --uses--> `FinancialStatements`  [INFERRED]
  tests/agents/test_supervisor_graph.py → app/models.py
- `_FanOutState` --uses--> `FinancialStatements`  [INFERRED]
  tests/agents/test_supervisor_graph.py → app/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Project Quality Contract** — _claude_rules_code_style_code_style, _claude_rules_testing_testing, _github_pull_request_template_verification, _pre_commit_config_pre_commit_quality_gates [INFERRED 0.95]
- **Containerized Application Stack** — docker_compose_postgres, docker_compose_backend, docker_compose_frontend [EXTRACTED 1.00]

## Communities (65 total, 9 thin omitted)

### Community 0 - "Financial Data Sources"
Cohesion: 0.07
Nodes (55): fetch_financials(), _find_concept_value(), _find_raw_concept_value(), _find_total_revenue(), normalize_financials(), _optional_concept_value(), _period_column(), DataFrame (+47 more)

### Community 1 - "News and Report Models"
Cohesion: 0.06
Nodes (66): News/Sentiment Agent entry point: ticker in, aggregated sentiment out. Never rai, run_news_sentiment(), build_report_writer_graph(), _get_report_llm(), AnalystReport, CompiledStateGraph, FundamentalRatios, Runnable (+58 more)

### Community 2 - "Supervisor Orchestration"
Cohesion: 0.06
Nodes (45): answer_filing_question(), build_filings_rag_graph(), FilingsRAGState, _generate(), _generation_prompt(), _get_generation_llm(), _get_rerank_client(), _grade_documents() (+37 more)

### Community 3 - "Report Writer Graph"
Cohesion: 0.14
Nodes (35): find_unsupported_report_numbers(), GuardrailViolation, _model_numbers(), _numeric_leaves(), _presidio_analyzer(), AnalystReport, Any, BaseModel (+27 more)

### Community 4 - "Streaming Supervisor API"
Cohesion: 0.06
Nodes (60): _apply_invariant(), build_supervisor_graph(), _data_ingestion(), _deterministic_next(), _get_routing_llm(), _has_run(), init_supervisor_graph(), BaseCheckpointSaver (+52 more)

### Community 5 - "Analyst Team Pipeline"
Cohesion: 0.06
Nodes (73): AnalystTeamState, build_analyst_team_graph(), _critic(), _critic_updates(), _fan_out(), _financials_branch(), _guardrails(), _hitl() (+65 more)

### Community 6 - "Valuation Analysis"
Cohesion: 0.06
Nodes (61): get_filings(), get_fundamentals(), Fetch recent regulatory filings (10-K, 10-Q) for a ticker., Fetch fundamental financial data (P/E, EPS, ROE, etc.) for a ticker., build_valuation_graph(), _compare(), CompiledStateGraph, TypedDict (+53 more)

### Community 7 - "Filing Ingestion"
Cohesion: 0.05
Nodes (54): AdaptiveRouter, Routes an incoming query to the appropriate sub-agent (valuation, sentiment, fil, Decide which agent(s) should handle the request and dispatch it., ChatRequest, ChatResponse, Chunk, _coerce_str_list(), FilingDocument (+46 more)

### Community 8 - "XBRL Cache"
Cohesion: 0.11
Nodes (38): _cached(), _companyfact_values(), _companyfacts_rows(), _concept_parts(), _date(), _decimal(), _decimals(), _dimensional_facts() (+30 more)

### Community 9 - "React Analysis UI"
Cohesion: 0.10
Nodes (25): App(), isAnalystReport(), formatValue(), GROUPS, RatiosCard(), Stat, StatTile(), ReportCard() (+17 more)

### Community 10 - "Frontend Dependencies"
Cohesion: 0.06
Nodes (35): @emotion/react, @emotion/styled, dependencies, @emotion/react, @emotion/styled, @mui/icons-material, @mui/material, react (+27 more)

### Community 11 - "News Sentiment Graph"
Cohesion: 0.11
Nodes (28): build_news_sentiment_graph(), _get_sentiment_llm(), _neutral_result(), NewsSentimentState, CompiledStateGraph, Runnable, TypedDict, News/Sentiment Agent subgraph: ticker in, aggregated sentiment out. Both nodes (+20 more)

### Community 12 - "Team Analysis Tests"
Cohesion: 0.24
Nodes (15): fetch_financials(), _latest_column(), DataFrame, Fetch and normalize income statement, balance sheet, and cash flow via yfinance., _value(), Series, _make_fake_ticker(), MonkeyPatch (+7 more)

### Community 13 - "Weaviate Retrieval Tests"
Cohesion: 0.06
Nodes (50): LangChain tool wrapper around the Weaviate retriever for agent use., vector_search_tool(), _embed_documents(), Semantic retriever backed by a Weaviate Cloud collection. Vectors are always, Embed and upsert documents. Re-adding a document with the same `id` overwrites, Embed `query` and run a near-vector search, optionally filtered by exact-match, WeaviateRetriever, Document (+42 more)

### Community 14 - "Ingestion Fallback Graph"
Cohesion: 0.16
Nodes (19): build_ingestion_graph(), IngestionState, CompiledStateGraph, TypedDict, Build the DataIngestionAgent subgraph: ticker in, financials out. Fallback chain, _route_after_edgartools(), _route_after_sec_edgar(), _try_edgartools() (+11 more)

### Community 15 - "Financial Models"
Cohesion: 0.18
Nodes (17): BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement, A single-period income statement., A single-period balance sheet., A single-period cash flow statement., Normalized income statement, balance sheet, and cash flow statement for a ticker (+9 more)

### Community 16 - "TypeScript Configuration"
Cohesion: 0.10
Nodes (20): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+12 more)

### Community 17 - "Adaptive Query Router"
Cohesion: 0.23
Nodes (15): _fetch_ratios(), _fetch_report(), _fetch_supervisor_ratios(), AnalystReport, BaseModel, FundamentalRatios, Stream DataIngestionAgent + RatioEngine progress for a ticker via SSE., Stream multi-agent Supervisor (DataIngestionAgent -> RatioAnalysisAgent) progres (+7 more)

### Community 19 - "Shared Test Fixtures"
Cohesion: 0.43
Nodes (6): MonkeyPatch, _statements(), test_stream_analysis_returns_error_event_on_source_unavailable(), test_stream_analysis_returns_result_event_on_success(), test_stream_fundamentals_returns_result_event_on_success(), test_stream_report_returns_result_event_on_success()

### Community 20 - "Ratio Engine"
Cohesion: 0.20
Nodes (10): FundamentalRatios, RatioEngine, Computes fundamental ratios from financial statements., Pure computation of all ratios from an already-fetched FinancialStatements snaps, Fetch financials for `ticker` via the ingestion subgraph, then compute ratios., _safe_div(), MonkeyPatch, test_compute_all_fetches_via_ingestion_then_computes() (+2 more)

### Community 24 - "Ratio Analysis Graph"
Cohesion: 0.27
Nodes (9): build_ratio_analysis_graph(), _compute(), CompiledStateGraph, FundamentalRatios, TypedDict, RatioAnalysisState, Ratio Analysis Agent subgraph: financials in, ratios out. A thin wrapper around, Ratio Analysis Agent entry point: financials in, ratios out. (+1 more)

### Community 26 - "Ingestion Tests"
Cohesion: 0.35
Nodes (10): DataIngestionAgent entry point: ticker in, financials out., run_ingestion(), _mock_tracer(), MonkeyPatch, A source with a partial statement raises SourceUnavailableError (adapter-level, test_all_sources_fail_raises_and_logs_twice(), test_edgar_cache_success_short_circuits(), test_falls_through_to_sec_and_logs_once() (+2 more)

### Community 28 - "Lifespan Tests"
Cohesion: 0.24
Nodes (6): _FakePostgresSaver, Exception, MonkeyPatch, Fail-fast on an unreachable/broken Postgres must not leak the connection pool., test_lifespan_closes_pool_even_if_checkpointer_setup_fails(), test_lifespan_opens_pool_inits_graph_and_closes_pool_on_exit()

### Community 29 - "Project Architecture Docs"
Cohesion: 0.10
Nodes (19): Analyst Team (News/Sentiment + Valuation + Report-Writer + Critic), Conventions, DataIngestionAgent / RatioEngine, Filings RAG pipeline, graphify, Multi-Agent Supervisor (Data Ingestion + Ratio Analysis), Run, Stack (+11 more)

### Community 30 - "Conversation Memory"
Cohesion: 0.25
Nodes (4): ConversationStore, Append a message to the conversation history., Return the full conversation history., Persists and retrieves multi-turn conversation history.

### Community 31 - "Semantic Response Cache"
Cohesion: 0.25
Nodes (4): Return a cached response if a semantically similar query exists., Store a query/response pair in the cache., Caches query/response pairs keyed by semantic similarity., SemanticCache

### Community 32 - "Token Cost Tracking"
Cohesion: 0.33
Nodes (3): CostTracker, Record token usage for a model call., Tracks token usage and estimated cost per request.

### Community 33 - "Prompt Registry"
Cohesion: 0.33
Nodes (3): PromptRegistry, Return the prompt template registered under `name`., Lookup and versioning for prompt templates.

### Community 34 - "Container Services"
Cohesion: 0.50
Nodes (4): Backend Service, Frontend Service, Postgres Service, Stock Fundamental Analyser HTML Shell

### Community 35 - "Quality Gates"
Cohesion: 0.67
Nodes (3): Testing Conventions, Pull Request Verification Checklist, Pre-commit Quality Gates

## Knowledge Gaps
- **66 isolated node(s):** `Stack`, `Run`, `Conventions`, `Multi-Agent Supervisor (Data Ingestion + Ratio Analysis)`, `Analyst Team (News/Sentiment + Valuation + Report-Writer + Critic)` (+61 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SourceUnavailableError` connect `Financial Data Sources` to `Streaming Supervisor API`, `Analyst Team Pipeline`, `Valuation Analysis`, `Filing Ingestion`, `XBRL Cache`, `Team Analysis Tests`, `Ingestion Fallback Graph`, `Adaptive Query Router`, `Shared Test Fixtures`, `Ingestion Tests`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `sanitize_ticker()` connect `Valuation Analysis` to `Financial Data Sources`, `News and Report Models`, `Supervisor Orchestration`, `Report Writer Graph`, `Streaming Supervisor API`, `Analyst Team Pipeline`, `XBRL Cache`, `News Sentiment Graph`, `Team Analysis Tests`, `Ingestion Fallback Graph`, `Adaptive Query Router`, `Ratio Engine`, `Ingestion Tests`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `FinancialStatements` connect `Financial Models` to `Financial Data Sources`, `News and Report Models`, `Report Writer Graph`, `Streaming Supervisor API`, `Analyst Team Pipeline`, `Filing Ingestion`, `XBRL Cache`, `Team Analysis Tests`, `Ingestion Fallback Graph`, `Shared Test Fixtures`, `Ratio Engine`, `Ratio Analysis Graph`, `Ingestion Tests`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `FinancialStatements` (e.g. with `AnalystTeamState` and `IngestionState`) actually correct?**
  _`FinancialStatements` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `SourceUnavailableError` (e.g. with `test_all_sources_fail_raises_and_logs_twice()` and `test_ingestion_failure_raises_source_unavailable()`) actually correct?**
  _`SourceUnavailableError` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `Document` (e.g. with `FilingsRAGState` and `WeaviateRetriever`) actually correct?**
  _`Document` has 16 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Stack`, `Run`, `Conventions` to the rest of the system?**
  _66 weakly-connected nodes found - possible documentation gaps or missing edges._