from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import ChatRequest, ChatResponse


class AdaptiveRouter:
    """Routes an incoming query to the appropriate sub-agent (valuation, sentiment, filings, etc.)."""

    def __init__(self) -> None:
        pass

    async def route(self, request: ChatRequest) -> ChatResponse:
        """Decide which agent(s) should handle the request and dispatch it."""
        raise NotImplementedError
