from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import ChatRequest, ChatResponse


class RagPipeline:
    """Retrieval-augmented generation pipeline orchestrating retriever + LLM."""

    def __init__(self) -> None:
        pass

    async def run(self, request: ChatRequest) -> ChatResponse:
        """Execute retrieval, context assembly, and generation."""
        raise NotImplementedError
