from __future__ import annotations

import pytest

from app.models import Document
from app.services.filings.retriever import FilingsRAGRetriever


class _FakeWeaviateRetriever:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.result = [Document(id="d1", content="apple risk", metadata={"ticker": "AAPL"})]

    def retrieve(self, query: str, k: int = 6, filters: dict[str, str] | None = None) -> list[Document]:
        self.calls.append({"query": query, "k": k, "filters": filters})
        return self.result


@pytest.mark.asyncio
async def test_retrieve_always_filters_by_ticker() -> None:
    fake = _FakeWeaviateRetriever()
    retriever = FilingsRAGRetriever(fake)

    await retriever.retrieve("What did management say about AI?", ticker="AAPL")

    assert fake.calls[0]["filters"] == {"ticker": "AAPL"}


@pytest.mark.asyncio
async def test_retrieve_adds_optional_form_type_and_period_filters() -> None:
    fake = _FakeWeaviateRetriever()
    retriever = FilingsRAGRetriever(fake)

    await retriever.retrieve("question", ticker="AAPL", form_type="10-K", period="2024-09-28")

    assert fake.calls[0]["filters"] == {"ticker": "AAPL", "form_type": "10-K", "period": "2024-09-28"}


@pytest.mark.asyncio
async def test_retrieve_passes_through_k_and_returns_documents() -> None:
    fake = _FakeWeaviateRetriever()
    retriever = FilingsRAGRetriever(fake)

    results = await retriever.retrieve("question", ticker="AAPL", k=3)

    assert fake.calls[0]["k"] == 3
    assert results == fake.result
