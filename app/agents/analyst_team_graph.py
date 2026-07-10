from __future__ import annotations

import operator
from typing import Annotated, TypedDict, cast
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from app.agents.news_sentiment_graph import run_news_sentiment
from app.agents.report_writer_graph import run_report_writer
from app.agents.supervisor_graph import run_supervisor_analysis
from app.agents.valuation_graph import run_valuation
from app.models import (
    AnalystReport,
    FinancialStatements,
    FundamentalRatios,
    NewsSentimentResult,
    ValuationResult,
)
from app.services.financial_sources import SourceUnavailableError


class AnalystTeamState(TypedDict):
    ticker: str
    financials: FinancialStatements | None
    ratios: FundamentalRatios | None
    sentiment: NewsSentimentResult | None
    valuation: ValuationResult | None
    report: AnalystReport | None
    messages: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]


def _fan_out(state: AnalystTeamState) -> list[Send]:
    return [Send("financials_branch", state), Send("news_branch", state)]


async def _financials_branch(state: AnalystTeamState, config: RunnableConfig) -> dict[str, object]:
    # Returns only the keys this branch actually changes -- financials_branch and
    # news_branch run concurrently in the same superstep, so returning unchanged scalar
    # keys (e.g. `ticker`, which has no reducer) from both would raise InvalidUpdateError.
    ticker = state["ticker"]
    parent_thread_id = config.get("configurable", {}).get("thread_id", ticker)
    try:
        result = await run_supervisor_analysis(
            ticker, thread_id=f"{parent_thread_id}:financials", config=config
        )
        return {
            "financials": result["financials"],
            "ratios": result["ratios"],
            "messages": ["financials_branch: completed"],
        }
    except SourceUnavailableError as exc:
        return {
            "errors": [f"financials_branch: {exc}"],
            "messages": [f"financials_branch: failed - {exc}"],
        }


async def _news_branch(state: AnalystTeamState) -> dict[str, object]:
    sentiment = await run_news_sentiment(state["ticker"])  # never raises, degrades to neutral
    return {"sentiment": sentiment, "messages": ["news_branch: completed"]}


async def _valuation(state: AnalystTeamState) -> dict[str, object]:
    valuation = await run_valuation(state["ticker"])
    return {"valuation": valuation, "messages": ["valuation: completed"]}


async def _report_writer(state: AnalystTeamState) -> dict[str, object]:
    report = await run_report_writer(
        ticker=state["ticker"],
        financials=state["financials"],
        ratios=state["ratios"],
        sentiment=state["sentiment"],
        valuation=state["valuation"],
    )
    return {"report": report, "messages": ["report_writer: completed"]}


def build_analyst_team_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """5-agent analyst team: fans out Data-Ingestion+Ratio-Analysis (reusing the existing
    2-agent supervisor as a black-box branch) and News/Sentiment concurrently via
    LangGraph's Send API, converges before Valuation, then Report-Writer. No LLM-driven
    routing at this level -- the pipeline shape is fully deterministic (fan-out -> valuation
    -> report-writer), unlike the reused supervisor branch's own internal routing."""
    graph = StateGraph(AnalystTeamState)
    graph.add_node("financials_branch", _financials_branch)
    graph.add_node("news_branch", _news_branch)
    graph.add_node("valuation", _valuation)
    graph.add_node("report_writer", _report_writer)
    graph.add_conditional_edges(START, _fan_out, ["financials_branch", "news_branch"])
    graph.add_edge("financials_branch", "valuation")
    graph.add_edge("news_branch", "valuation")
    graph.add_edge("valuation", "report_writer")
    graph.add_edge("report_writer", END)
    return graph.compile(checkpointer=checkpointer)


_compiled_graph: CompiledStateGraph | None = None


def init_analyst_team_graph(checkpointer: BaseCheckpointSaver) -> None:
    """Compile and register the analyst team graph; must be called once during app startup
    (see app.core.lifespan), using the same checkpointer as the reused supervisor graph."""
    global _compiled_graph
    _compiled_graph = build_analyst_team_graph(checkpointer)


async def run_team_analysis(
    ticker: str, *, thread_id: str | None = None, config: RunnableConfig | None = None
) -> AnalystTeamState:
    """Analyst team entry point: ticker in, final AnalystTeamState (with `report`) out.

    `thread_id`/`config` let a caller set a stable checkpoint thread when resume semantics
    are wanted; otherwise each call gets its own thread so concurrent same-ticker requests
    don't share state."""
    assert _compiled_graph is not None, (
        "init_analyst_team_graph() must be called before run_team_analysis()"
    )
    merged_config: RunnableConfig = {
        **(config or {}),
        "configurable": {
            **(config or {}).get("configurable", {}),
            "thread_id": thread_id or f"{ticker}:team:{uuid4().hex}",
        },
    }
    config = merged_config
    initial_state: AnalystTeamState = {
        "ticker": ticker,
        "financials": None,
        "ratios": None,
        "sentiment": None,
        "valuation": None,
        "report": None,
        "messages": [],
        "errors": [],
    }
    return cast(AnalystTeamState, await _compiled_graph.ainvoke(initial_state, config))
