from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Document


async def vector_search_tool(query: str, k: int = 6) -> list[Document]:
    """LangChain tool wrapper around the Weaviate retriever for agent use."""
    raise NotImplementedError
