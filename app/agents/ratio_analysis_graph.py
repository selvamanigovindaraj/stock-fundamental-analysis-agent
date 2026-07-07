from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.models import FinancialStatements, FundamentalRatios
from app.services.ratio_engine import RatioEngine


class RatioAnalysisState(TypedDict):
    financials: FinancialStatements
    ratios: FundamentalRatios | None


async def _compute(state: RatioAnalysisState) -> RatioAnalysisState:
    return {**state, "ratios": RatioEngine.compute(state["financials"])}


def build_ratio_analysis_graph() -> CompiledStateGraph:
    """Ratio Analysis Agent subgraph: financials in, ratios out. A thin wrapper around the
    pure RatioEngine.compute so this worker satisfies the same compiled-StateGraph shape as
    the Data Ingestion Agent."""
    graph = StateGraph(RatioAnalysisState)
    graph.add_node("compute", _compute)
    graph.add_edge(START, "compute")
    graph.add_edge("compute", END)
    return graph.compile()


_compiled_graph = build_ratio_analysis_graph()


async def run_ratio_analysis(financials: FinancialStatements) -> FundamentalRatios:
    """Ratio Analysis Agent entry point: financials in, ratios out."""
    result = await _compiled_graph.ainvoke({"financials": financials, "ratios": None})
    ratios = result["ratios"]
    if ratios is None:
        raise ValueError(f"ratio computation failed to produce a result for {financials.ticker}")
    return ratios
