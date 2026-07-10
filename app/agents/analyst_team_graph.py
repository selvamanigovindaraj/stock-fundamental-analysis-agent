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
from app.agents.report_critic_graph import run_report_critic
from app.agents.report_writer_graph import run_report_writer
from app.agents.supervisor_graph import run_supervisor_analysis
from app.agents.valuation_graph import run_valuation
from app.models import (
    AnalystReport,
    CRITIC_QUALITY_THRESHOLD,
    CriticReview,
    FinancialStatements,
    FundamentalRatios,
    NewsSentimentResult,
    ValuationResult,
)
from app.services.financial_sources import SourceUnavailableError

_MAX_REVISIONS = 3


class AnalystTeamState(TypedDict):
    ticker: str
    financials: FinancialStatements | None
    ratios: FundamentalRatios | None
    sentiment: NewsSentimentResult | None
    valuation: ValuationResult | None
    report: AnalystReport | None
    first_report: AnalystReport | None
    critic_review: CriticReview | None
    first_critic_review: CriticReview | None
    revision_instructions: str | None
    revision_count: int
    quality_flag: str | None
    hitl_status: str | None
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
        previous_report=state["report"],
        revision_instructions=state["revision_instructions"],
    )
    updates: dict[str, object] = {
        "report": report,
        "revision_instructions": None,
        "messages": ["report_writer: completed"],
    }
    if state["first_report"] is None:
        updates["first_report"] = report
    return updates


def _source_urls(state: AnalystTeamState) -> list[str]:
    sentiment = state["sentiment"]
    return [article.url for article in sentiment.articles] if sentiment else []


def _critic_updates(state: AnalystTeamState, review: CriticReview) -> dict[str, object]:
    needs_revision = review.score < CRITIC_QUALITY_THRESHOLD
    revision_count = state["revision_count"] + 1 if needs_revision else state["revision_count"]
    quality_flag = None
    if not needs_revision:
        quality_flag = "accepted"
    elif revision_count >= _MAX_REVISIONS:
        quality_flag = "max_revisions_reached"

    updates: dict[str, object] = {
        "critic_review": review,
        "revision_count": revision_count,
        "revision_instructions": review.revision_instructions if needs_revision else None,
        "quality_flag": quality_flag,
        "messages": [f"critic: {review.verdict} ({review.score:.2f})"],
    }
    if state["first_critic_review"] is None:
        updates["first_critic_review"] = review
    return updates


async def _critic(state: AnalystTeamState) -> dict[str, object]:
    report = state["report"]
    if report is None:
        raise ValueError("critic invoked before report_writer produced a report")
    try:
        review = await run_report_critic(
            ticker=state["ticker"],
            report=report,
            ratios=state["ratios"],
            source_urls=_source_urls(state),
        )
    except Exception as exc:  # noqa: BLE001 - a critic outage should not block HITL review
        return {
            "critic_review": CriticReview(
                score=0.0,
                verdict="accept",
                revision_instructions=f"Critic failed: {exc}",
            ),
            "quality_flag": "critic_failed",
            "errors": [f"critic: {exc}"],
            "messages": [f"critic: failed - {exc}"],
        }

    return _critic_updates(state, review)


def _route_after_critic(state: AnalystTeamState) -> str:
    if state["quality_flag"] in {"accepted", "max_revisions_reached", "critic_failed"}:
        return "hitl"
    return "report_writer"


async def _hitl(state: AnalystTeamState) -> dict[str, object]:
    return {"hitl_status": "ready", "messages": ["hitl: ready"]}


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
    graph.add_node("critic", _critic)
    graph.add_node("hitl", _hitl)
    graph.add_conditional_edges(START, _fan_out, ["financials_branch", "news_branch"])
    graph.add_edge("financials_branch", "valuation")
    graph.add_edge("news_branch", "valuation")
    graph.add_edge("valuation", "report_writer")
    graph.add_edge("report_writer", "critic")
    graph.add_conditional_edges(
        "critic", _route_after_critic, {"report_writer": "report_writer", "hitl": "hitl"}
    )
    graph.add_edge("hitl", END)
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
        "first_report": None,
        "critic_review": None,
        "first_critic_review": None,
        "revision_instructions": None,
        "revision_count": 0,
        "quality_flag": None,
        "hitl_status": None,
        "messages": [],
        "errors": [],
    }
    return cast(AnalystTeamState, await _compiled_graph.ainvoke(initial_state, config))
