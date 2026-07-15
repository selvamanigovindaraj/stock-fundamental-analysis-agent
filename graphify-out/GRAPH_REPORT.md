# Graph Report - .  (2026-07-15)

## Corpus Check
- Corpus is ~36,039 words - fits in a single context window. You may not need a graph.

## Summary
- 1009 nodes · 2405 edges · 70 communities (62 shown, 8 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 188 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

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
- Filings RAG Tests
- Filings RAG Graph
- Filing QA Interface
- Ratio Analysis Graph
- Weaviate Retriever
- Ingestion Tests
- Collection Test Doubles
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
- `Pull Request Verification Checklist` --semantically_similar_to--> `Testing Conventions`  [INFERRED] [semantically similar]
  .github/pull_request_template.md → .claude/rules/testing.md
- `Stock Fundamental Analyser Claude Instructions` --semantically_similar_to--> `Stock Fundamental Analyser Agent Instructions`  [INFERRED] [semantically similar]
  CLAUDE.md → AGENTS.md
- `_FakeCollection` --uses--> `WeaviateRetriever`  [INFERRED]
  tests/components/test_retriever.py → app/components/retriever.py
- `_FakeData` --uses--> `WeaviateRetriever`  [INFERRED]
  tests/components/test_retriever.py → app/components/retriever.py
- `_FakeQuery` --uses--> `WeaviateRetriever`  [INFERRED]
  tests/components/test_retriever.py → app/components/retriever.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Project Quality Contract** — _claude_rules_code_style_code_style, _claude_rules_testing_testing, _github_pull_request_template_verification, _pre_commit_config_pre_commit_quality_gates [INFERRED 0.95]
- **Containerized Application Stack** — docker_compose_postgres, docker_compose_backend, docker_compose_frontend [EXTRACTED 1.00]

## Communities (70 total, 8 thin omitted)

### Community 0 - "Financial Data Sources"
Cohesion: 0.06
Nodes (64): fetch_financials(), _find_concept_value(), _find_raw_concept_value(), _find_total_revenue(), normalize_financials(), _optional_concept_value(), _period_column(), DataFrame (+56 more)

### Community 1 - "News and Report Models"
Cohesion: 0.07
Nodes (53): News/Sentiment Agent entry point: ticker in, aggregated sentiment out. Never rai, run_news_sentiment(), FundamentalRatios, Report-Writer Agent entry point: all upstream agent outputs in, final AnalystRep, run_report_writer(), ArticleSentiment, NewsSentimentResult, LLM-scored sentiment for a single news article. (+45 more)

### Community 2 - "Supervisor Orchestration"
Cohesion: 0.07
Nodes (49): init_analyst_team_graph(), Compile and register the analyst team graph; must be called once during app star, _apply_invariant(), build_supervisor_graph(), _data_ingestion(), _deterministic_next(), _get_routing_llm(), _has_run() (+41 more)

### Community 3 - "Report Writer Graph"
Cohesion: 0.08
Nodes (54): build_report_writer_graph(), _get_report_llm(), AnalystReport, CompiledStateGraph, Runnable, TypedDict, Report-Writer Agent subgraph: all upstream agent outputs in, final AnalystReport, _report_prompt() (+46 more)

### Community 4 - "Streaming Supervisor API"
Cohesion: 0.07
Nodes (50): BaseModel, RunnableConfig, Supervisor entry point: ticker in, final SupervisorState out. Raises     SourceU, Supervisor's structured-output routing decision -- graph-internal plumbing, not, RoutingDecision, run_supervisor_analysis(), _fetch_ratios(), _fetch_report() (+42 more)

### Community 5 - "Analyst Team Pipeline"
Cohesion: 0.09
Nodes (46): AnalystTeamState, build_analyst_team_graph(), _critic(), _critic_updates(), _fan_out(), _financials_branch(), _guardrails(), _hitl() (+38 more)

### Community 6 - "Valuation Analysis"
Cohesion: 0.09
Nodes (45): build_valuation_graph(), _compare(), CompiledStateGraph, TypedDict, Valuation Agent subgraph: ticker in, sector-relative valuation verdict out. Thin, _safe_fetch_market_ratios(), ValuationState, Live-fetched sector-peer median P/E, P/B, and ROE for a ticker's sector. (+37 more)

### Community 7 - "Filing Ingestion"
Cohesion: 0.09
Nodes (37): Chunk, FilingDocument, A single chunk of a FilingDocument, ready for embedding., A single extracted section (MD&A or Risk Factors) from one 10-K/10-Q filing., chunk_documents(), Split each FilingDocument's section text into overlapping chunks, propagating me, _extract_sections(), fetch_recent_filings() (+29 more)

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
Cohesion: 0.14
Nodes (29): Analyst team entry point: ticker in, final AnalystTeamState (with `report`) out., run_team_analysis(), _FakeCompiledTeamGraph, _financials(), _init_with_in_memory_checkpointer(), AnalystReport, FundamentalRatios, MonkeyPatch (+21 more)

### Community 13 - "Weaviate Retrieval Tests"
Cohesion: 0.17
Nodes (20): Semantic retriever backed by a Weaviate Cloud collection. Vectors are always, WeaviateRetriever, _fake_client(), _FakeClient, _FakeCollectionsManager, _FakeEmbeddings, _FakeObject, _FakeQueryResult (+12 more)

### Community 14 - "Ingestion Fallback Graph"
Cohesion: 0.16
Nodes (19): build_ingestion_graph(), IngestionState, CompiledStateGraph, TypedDict, Build the DataIngestionAgent subgraph: ticker in, financials out. Fallback chain, _route_after_edgartools(), _route_after_sec_edgar(), _try_edgartools() (+11 more)

### Community 15 - "Financial Models"
Cohesion: 0.16
Nodes (21): FundamentalRatios, Ratio Analysis Agent entry point: financials in, ratios out., run_ratio_analysis(), BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement, A single-period income statement. (+13 more)

### Community 16 - "TypeScript Configuration"
Cohesion: 0.10
Nodes (20): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+12 more)

### Community 17 - "Adaptive Query Router"
Cohesion: 0.17
Nodes (13): AdaptiveRouter, Routes an incoming query to the appropriate sub-agent (valuation, sentiment, fil, Decide which agent(s) should handle the request and dispatch it., ChatRequest, ChatResponse, FilingsRAGAnswer, BaseModel, Answer to a natural-language question about a company's filings, with citations. (+5 more)

### Community 18 - "Vector Search Tooling"
Cohesion: 0.21
Nodes (12): LangChain tool wrapper around the Weaviate retriever for agent use., vector_search_tool(), Document, A retrieved or ingested document chunk., FilingsRAGRetriever, get_weaviate_retriever(), Module-level singleton WeaviateRetriever bound to the filings collection, shared, Retrieves filing-section chunks relevant to a natural-language question, always (+4 more)

### Community 19 - "Shared Test Fixtures"
Cohesion: 0.18
Nodes (12): fake_lifespan_postgres(), _FakeCheckpointer, make_financial_statements(), MonkeyPatch, Shared fixture builder -- used by test_supervisor_graph.py, test_analyst_team_gr, `TestClient(app)` triggers the real `app.core.lifespan.lifespan` on startup --, MonkeyPatch, _statements() (+4 more)

### Community 20 - "Ratio Engine"
Cohesion: 0.15
Nodes (12): FundamentalRatios, Pure computation of all ratios from an already-fetched FinancialStatements snaps, Fetch financials for `ticker` via the ingestion subgraph, then compute ratios., _safe_div(), LogCaptureFixture, Confirms the strict-mode-derived allowlist actually lets our checkpointed state, _statements(), test_checkpointed_financials_and_ratios_round_trip_without_warning() (+4 more)

### Community 21 - "Filings RAG Tests"
Cohesion: 0.26
Nodes (10): _docs(), _FakeGenerationLLM, _FakeRerankClient, _FakeRerankingObject, _FakeRerankResult, MonkeyPatch, _reset_singletons(), test_all_chunks_below_relevance_threshold_skips_generation() (+2 more)

### Community 22 - "Filings RAG Graph"
Cohesion: 0.25
Nodes (13): build_filings_rag_graph(), FilingsRAGState, _generate(), _generation_prompt(), _get_generation_llm(), _get_rerank_client(), _grade_documents(), AsyncClient (+5 more)

### Community 23 - "Filing QA Interface"
Cohesion: 0.20
Nodes (11): answer_filing_question(), Answer a natural-language question about `ticker`'s filings, with citations., filings_rag_tool(), Answer a natural-language question about a company's 10-K/10-Q filings -- their, _build_rows(), EvalRow, main(), _StubChatVertexAI (+3 more)

### Community 24 - "Ratio Analysis Graph"
Cohesion: 0.29
Nodes (10): build_ratio_analysis_graph(), _compute(), CompiledStateGraph, TypedDict, RatioAnalysisState, Ratio Analysis Agent subgraph: financials in, ratios out. A thin wrapper around, FundamentalRatios, Fundamental ratios computed from a FinancialStatements snapshot. (+2 more)

### Community 25 - "Weaviate Retriever"
Cohesion: 0.18
Nodes (7): _embed_documents(), _get_client(), Embed and upsert documents. Re-adding a document with the same `id` overwrites, Embed `query` and run a near-vector search, optionally filtered by exact-match, Collection, Embeddings, WeaviateClient

### Community 26 - "Ingestion Tests"
Cohesion: 0.35
Nodes (10): DataIngestionAgent entry point: ticker in, financials out., run_ingestion(), _mock_tracer(), MonkeyPatch, A source with a partial statement raises SourceUnavailableError (adapter-level, test_all_sources_fail_raises_and_logs_twice(), test_edgar_cache_success_short_circuits(), test_falls_through_to_sec_and_logs_once() (+2 more)

### Community 27 - "Collection Test Doubles"
Cohesion: 0.22
Nodes (3): _FakeCollection, _FakeData, _FakeQuery

### Community 28 - "Lifespan Tests"
Cohesion: 0.24
Nodes (6): _FakePostgresSaver, Exception, MonkeyPatch, Fail-fast on an unreachable/broken Postgres must not leak the connection pool., test_lifespan_closes_pool_even_if_checkpointer_setup_fails(), test_lifespan_opens_pool_inits_graph_and_closes_pool_on_exit()

### Community 29 - "Project Architecture Docs"
Cohesion: 0.29
Nodes (8): Analyst Team Pipeline, Filings RAG Pipeline, Multi-Agent Supervisor, Stock Fundamental Analyser Agent Instructions, Graphify Knowledge Graph Workflow, Stock Fundamental Analyser Claude Instructions, Critic Loop Quality Measurement, Stock Fundamental Analyser

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
- **52 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+47 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FinancialStatements` connect `Financial Models` to `Financial Data Sources`, `News and Report Models`, `Supervisor Orchestration`, `Report Writer Graph`, `Streaming Supervisor API`, `Analyst Team Pipeline`, `XBRL Cache`, `Team Analysis Tests`, `Ingestion Fallback Graph`, `Adaptive Query Router`, `Shared Test Fixtures`, `Ratio Engine`, `Ratio Analysis Graph`, `Ingestion Tests`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `SourceUnavailableError` connect `Financial Data Sources` to `Supervisor Orchestration`, `Streaming Supervisor API`, `Analyst Team Pipeline`, `Filing Ingestion`, `XBRL Cache`, `Team Analysis Tests`, `Ingestion Fallback Graph`, `Financial Models`, `Shared Test Fixtures`, `Ingestion Tests`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `sanitize_ticker()` connect `Report Writer Graph` to `Financial Data Sources`, `News and Report Models`, `Supervisor Orchestration`, `Streaming Supervisor API`, `Analyst Team Pipeline`, `Valuation Analysis`, `XBRL Cache`, `News Sentiment Graph`, `Team Analysis Tests`, `Ingestion Fallback Graph`, `Financial Models`, `Ratio Engine`, `Filings RAG Graph`, `Filing QA Interface`, `Ratio Analysis Graph`, `Ingestion Tests`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `FinancialStatements` (e.g. with `AnalystTeamState` and `IngestionState`) actually correct?**
  _`FinancialStatements` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `SourceUnavailableError` (e.g. with `test_all_sources_fail_raises_and_logs_twice()` and `test_ingestion_failure_raises_source_unavailable()`) actually correct?**
  _`SourceUnavailableError` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `Document` (e.g. with `FilingsRAGState` and `WeaviateRetriever`) actually correct?**
  _`Document` has 16 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _52 weakly-connected nodes found - possible documentation gaps or missing edges._