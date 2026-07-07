from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.models import ValuationResult
from app.services.sector_benchmarks import fetch_market_ratios, fetch_sector_benchmark
from app.services.valuation import compare_to_sector


class ValuationState(TypedDict):
    ticker: str
    result: ValuationResult | None


async def _compare(state: ValuationState) -> ValuationState:
    ticker = state["ticker"]
    (pe, pb, roe), benchmark = await asyncio.gather(
        fetch_market_ratios(ticker), fetch_sector_benchmark(ticker)
    )
    return {**state, "result": compare_to_sector(ticker, pe, pb, roe, benchmark)}


def build_valuation_graph() -> CompiledStateGraph:
    """Valuation Agent subgraph: ticker in, sector-relative valuation verdict out. Thin
    wrapper -- all deterministic comparison logic lives in app.services.valuation."""
    graph = StateGraph(ValuationState)
    graph.add_node("compare", _compare)
    graph.add_edge(START, "compare")
    graph.add_edge("compare", END)
    return graph.compile()


_compiled_graph = build_valuation_graph()


async def run_valuation(ticker: str) -> ValuationResult:
    """Valuation Agent entry point: ticker in, sector-relative valuation verdict out."""
    result = await _compiled_graph.ainvoke({"ticker": ticker, "result": None})
    valuation = result["result"]
    assert valuation is not None
    return valuation
