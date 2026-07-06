from __future__ import annotations

import asyncio

from langchain_voyageai import VoyageAIEmbeddings
from pydantic import SecretStr

from app.components.retriever import WeaviateRetriever
from app.config import get_settings
from app.models import Document

_weaviate_retriever: WeaviateRetriever | None = None


def get_weaviate_retriever() -> WeaviateRetriever:
    """Module-level singleton WeaviateRetriever bound to the filings collection, shared
    by both the ingestion (write) and question-answering (read) paths."""
    global _weaviate_retriever
    if _weaviate_retriever is None:
        settings = get_settings()
        embeddings = VoyageAIEmbeddings(
            model=settings.voyage_embedding_model, api_key=SecretStr(settings.voyage_api_key)
        )
        _weaviate_retriever = WeaviateRetriever(settings.weaviate_filings_collection, embeddings)
    return _weaviate_retriever


class FilingsRAGRetriever:
    """Retrieves filing-section chunks relevant to a natural-language question, always
    scoped to a specific ticker (and optionally form type / period)."""

    def __init__(self, weaviate_retriever: WeaviateRetriever | None = None) -> None:
        self._weaviate_retriever = weaviate_retriever or get_weaviate_retriever()

    async def retrieve(
        self,
        question: str,
        *,
        ticker: str,
        form_type: str | None = None,
        period: str | None = None,
        k: int = 6,
    ) -> list[Document]:
        filters = {"ticker": ticker}
        if form_type:
            filters["form_type"] = form_type
        if period:
            filters["period"] = period
        return await asyncio.to_thread(self._weaviate_retriever.retrieve, question, k, filters)
