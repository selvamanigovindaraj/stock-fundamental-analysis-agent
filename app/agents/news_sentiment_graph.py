from __future__ import annotations

import logging
from typing import TypedDict, cast

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr

from app.agents.tools.web_search import web_search_tool
from app.config import get_settings
from app.models import NewsSentimentResult

logger = logging.getLogger(__name__)


def _neutral_result(ticker: str) -> NewsSentimentResult:
    return NewsSentimentResult(
        ticker=ticker, sentiment="neutral", score=0.5, key_themes=[], articles=[]
    )


class NewsSentimentState(TypedDict):
    ticker: str
    articles: list[dict[str, str]]
    result: NewsSentimentResult | None


_sentiment_llm: Runnable[str, NewsSentimentResult] | None = None


def _get_sentiment_llm() -> Runnable[str, NewsSentimentResult]:
    global _sentiment_llm
    if _sentiment_llm is None:
        settings = get_settings()
        # deepseek_model_routing, not deepseek_model_generation -- with_structured_output
        # requires a non-thinking model (see CLAUDE.md); deepseek_model_generation is
        # configured as a thinking model (deepseek-v4-flash) and 400s on tool_choice.
        _sentiment_llm = cast(
            "Runnable[str, NewsSentimentResult]",
            ChatOpenAI(
                model=settings.deepseek_model_routing,
                api_key=SecretStr(settings.deepseek_api_key),
                base_url=settings.deepseek_base_url,
            ).with_structured_output(NewsSentimentResult, method="function_calling"),
        )
    return _sentiment_llm


async def _search(state: NewsSentimentState) -> NewsSentimentState:
    try:
        articles = await web_search_tool(f"{state['ticker']} stock news")
    except Exception:
        logger.exception("news search failed for %s", state["ticker"])
        articles = []
    return {**state, "articles": articles}


def _scoring_prompt(ticker: str, articles: list[dict[str, str]]) -> str:
    listing = "\n\n".join(
        f"[{i}] {a['title']} ({a['url']})\n{a['content']}" for i, a in enumerate(articles)
    )
    return (
        f"Score the sentiment of each of the following {len(articles)} news articles about "
        f"{ticker}, then aggregate them into an overall sentiment, score, and key themes.\n\n"
        f"{listing}"
    )


async def _score(state: NewsSentimentState) -> NewsSentimentState:
    ticker = state["ticker"]
    articles = state["articles"]
    if not articles:
        return {**state, "result": _neutral_result(ticker)}
    try:
        result = await _get_sentiment_llm().ainvoke(_scoring_prompt(ticker, articles))
    except Exception:
        logger.exception("news sentiment scoring failed for %s", ticker)
        result = _neutral_result(ticker)
    return {**state, "result": result}


def build_news_sentiment_graph() -> CompiledStateGraph:
    """News/Sentiment Agent subgraph: ticker in, aggregated sentiment out. Both nodes
    degrade to a neutral result on failure rather than raising -- a broken search or LLM
    call here should never abort the whole analyst team run."""
    graph = StateGraph(NewsSentimentState)
    graph.add_node("search", _search)
    graph.add_node("score", _score)
    graph.add_edge(START, "search")
    graph.add_edge("search", "score")
    graph.add_edge("score", END)
    return graph.compile()


_compiled_graph = build_news_sentiment_graph()


async def run_news_sentiment(ticker: str) -> NewsSentimentResult:
    """News/Sentiment Agent entry point: ticker in, aggregated sentiment out. Never raises."""
    result = await _compiled_graph.ainvoke({"ticker": ticker, "articles": [], "result": None})
    sentiment = result["result"]
    assert sentiment is not None
    return sentiment
