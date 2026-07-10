from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.analyst_team_graph import run_team_analysis
from app.agents.supervisor_graph import run_supervisor_analysis
from app.models import AnalystReport, FundamentalRatios
from app.services.financial_sources import SourceUnavailableError
from app.services.guardrails import GuardrailViolation, sanitize_ticker
from app.services.ratio_engine import RatioEngine

logger = logging.getLogger(__name__)

router = APIRouter()


def _validated_ticker(ticker: str) -> str:
    try:
        return sanitize_ticker(ticker)
    except GuardrailViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _sse_stream(
    ticker: str, compute: Callable[[str], Awaitable[BaseModel]]
) -> AsyncIterator[str]:
    yield f"event: started\ndata: {json.dumps({'ticker': ticker})}\n\n"
    try:
        ratios = await compute(ticker)
        yield f"event: result\ndata: {ratios.model_dump_json()}\n\n"
    except SourceUnavailableError as exc:
        yield f"event: error\ndata: {json.dumps({'ticker': ticker, 'error': str(exc)})}\n\n"
    except Exception:
        # Once the SSE response has started, FastAPI's normal exception handlers can no
        # longer convert a mid-stream failure into a clean HTTP error — without this, an
        # unexpected bug here would just cut the connection with no error event at all.
        logger.exception("unexpected error streaming analysis for %s", ticker)
        yield f"event: error\ndata: {json.dumps({'ticker': ticker, 'error': 'internal error'})}\n\n"


async def _fetch_ratios(ticker: str) -> FundamentalRatios:
    return await RatioEngine.compute_all(ticker)


async def _fetch_supervisor_ratios(ticker: str) -> FundamentalRatios:
    result = await run_supervisor_analysis(ticker)
    ratios = result["ratios"]
    assert ratios is not None  # guaranteed by run_supervisor_analysis's own contract
    return ratios


async def _fetch_report(ticker: str) -> AnalystReport:
    result = await run_team_analysis(ticker)
    report = result["report"]
    assert report is not None  # report_writer always runs, degraded inputs or not
    return report


@router.get("/fundamentals/{ticker}/stream")
async def stream_fundamentals(ticker: str) -> StreamingResponse:
    """Stream DataIngestionAgent + RatioEngine progress for a ticker via SSE."""
    ticker = _validated_ticker(ticker)
    return StreamingResponse(_sse_stream(ticker, _fetch_ratios), media_type="text/event-stream")


@router.get("/analysis/{ticker}/stream")
async def stream_analysis(ticker: str) -> StreamingResponse:
    """Stream multi-agent Supervisor (DataIngestionAgent -> RatioAnalysisAgent) progress for
    a ticker via SSE."""
    ticker = _validated_ticker(ticker)
    return StreamingResponse(
        _sse_stream(ticker, _fetch_supervisor_ratios), media_type="text/event-stream"
    )


@router.get("/report/{ticker}/stream")
async def stream_report(ticker: str) -> StreamingResponse:
    """Stream the full 5-agent analyst team (Data Ingestion + Ratio Analysis + News/Sentiment
    fan-out -> Valuation -> Report-Writer) progress for a ticker via SSE."""
    ticker = _validated_ticker(ticker)
    return StreamingResponse(_sse_stream(ticker, _fetch_report), media_type="text/event-stream")
