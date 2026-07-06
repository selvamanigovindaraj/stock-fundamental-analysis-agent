from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.services.financial_sources import SourceUnavailableError
from app.services.ratio_engine import RatioEngine

logger = logging.getLogger(__name__)

app = FastAPI(title="Multi Agent Stock Fundamental Analyser")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    raise NotImplementedError


@app.post("/chat")
async def chat() -> dict[str, str]:
    """Entry point for the multi-agent stock fundamental analysis pipeline."""
    raise NotImplementedError


async def _fundamentals_event_stream(ticker: str) -> AsyncIterator[str]:
    yield f"event: started\ndata: {json.dumps({'ticker': ticker})}\n\n"
    try:
        ratios = await RatioEngine.compute_all(ticker)
        yield f"event: result\ndata: {ratios.model_dump_json()}\n\n"
    except SourceUnavailableError as exc:
        yield f"event: error\ndata: {json.dumps({'ticker': ticker, 'error': str(exc)})}\n\n"
    except Exception:
        # Once the SSE response has started, FastAPI's normal exception handlers can no
        # longer convert a mid-stream failure into a clean HTTP error — without this, an
        # unexpected bug here would just cut the connection with no error event at all.
        logger.exception("unexpected error streaming fundamentals for %s", ticker)
        yield f"event: error\ndata: {json.dumps({'ticker': ticker, 'error': 'internal error'})}\n\n"


@app.get("/fundamentals/{ticker}/stream")
async def stream_fundamentals(ticker: str) -> StreamingResponse:
    """Stream DataIngestionAgent + RatioEngine progress for a ticker via SSE."""
    return StreamingResponse(_fundamentals_event_stream(ticker), media_type="text/event-stream")
