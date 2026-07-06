from __future__ import annotations

import pytest

from app.models import Chunk, FilingDocument
from app.services.filings import ingest


class _FakeWeaviateRetriever:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add_documents(self, documents: list[object]) -> None:
        self.added.extend(documents)


@pytest.mark.asyncio
async def test_ingest_ticker_filings_wires_download_chunk_and_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filing_doc = FilingDocument(
        ticker="AAPL",
        form_type="10-K",
        period="2024-09-28",
        accession_no="0000320193-24-000123",
        filing_url="https://example.com/aapl.htm",
        section="risk_factors",
        text="A" * 3000,
    )

    async def fake_fetch(ticker: str) -> list[FilingDocument]:
        assert ticker == "AAPL"
        return [filing_doc]

    fake_retriever = _FakeWeaviateRetriever()
    monkeypatch.setattr(ingest, "fetch_recent_filings", fake_fetch)
    monkeypatch.setattr(ingest, "get_weaviate_retriever", lambda: fake_retriever)

    count = await ingest.ingest_ticker_filings("AAPL")

    assert count > 0
    assert len(fake_retriever.added) == count
    first = fake_retriever.added[0]
    assert first.metadata["ticker"] == "AAPL"
    assert first.metadata["accession_no"] == "0000320193-24-000123"
    assert first.metadata["section"] == "risk_factors"


@pytest.mark.asyncio
async def test_ingest_ticker_filings_produces_deterministic_ids_across_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-ingesting the same filing must produce the same chunk ids, so WeaviateRetriever's
    upsert-by-id can overwrite in place instead of duplicating."""
    filing_doc = FilingDocument(
        ticker="AAPL",
        form_type="10-K",
        period="2024-09-28",
        accession_no="0000320193-24-000123",
        filing_url="https://example.com/aapl.htm",
        section="risk_factors",
        text="B" * 3000,
    )

    async def fake_fetch(ticker: str) -> list[FilingDocument]:
        return [filing_doc]

    retriever_1 = _FakeWeaviateRetriever()
    monkeypatch.setattr(ingest, "fetch_recent_filings", fake_fetch)
    monkeypatch.setattr(ingest, "get_weaviate_retriever", lambda: retriever_1)
    await ingest.ingest_ticker_filings("AAPL")

    retriever_2 = _FakeWeaviateRetriever()
    monkeypatch.setattr(ingest, "get_weaviate_retriever", lambda: retriever_2)
    await ingest.ingest_ticker_filings("AAPL")

    ids_1 = [d.id for d in retriever_1.added]
    ids_2 = [d.id for d in retriever_2.added]
    assert ids_1 == ids_2


def test_chunk_to_document_maps_all_metadata() -> None:
    chunk = Chunk(
        text="some text",
        ticker="AAPL",
        form_type="10-K",
        period="2024-09-28",
        section="mdna",
        accession_no="0000320193-24-000123",
        filing_url="https://example.com/aapl.htm",
        chunk_index=2,
    )

    document = ingest._chunk_to_document(chunk)

    assert document.content == "some text"
    assert document.metadata == {
        "ticker": "AAPL",
        "form_type": "10-K",
        "period": "2024-09-28",
        "section": "mdna",
        "accession_no": "0000320193-24-000123",
        "filing_url": "https://example.com/aapl.htm",
    }
