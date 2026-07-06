from __future__ import annotations

import asyncio

from app.models import Chunk, Document
from app.services.filings.chunker import chunk_documents
from app.services.filings.downloader import fetch_recent_filings
from app.services.filings.retriever import get_weaviate_retriever


def _chunk_to_document(chunk: Chunk) -> Document:
    # Deterministic id so re-ingesting the same filing overwrites its chunks in place
    # (WeaviateRetriever.add_documents upserts by id) rather than duplicating them.
    doc_id = f"{chunk.ticker}:{chunk.accession_no}:{chunk.section}:{chunk.chunk_index}"
    return Document(
        id=doc_id,
        content=chunk.text,
        metadata={
            "ticker": chunk.ticker,
            "form_type": chunk.form_type,
            "period": chunk.period,
            "section": chunk.section,
            "accession_no": chunk.accession_no,
            "filing_url": chunk.filing_url,
        },
    )


async def ingest_ticker_filings(ticker: str) -> int:
    """Fetch, chunk, embed, and store the most recent 10-K/10-Q filings for `ticker`.
    Idempotent -- safe to re-run (re-ingesting the same filing overwrites its chunks in
    place instead of duplicating them)."""
    filing_documents = await fetch_recent_filings(ticker)
    chunks = chunk_documents(filing_documents)
    documents = [_chunk_to_document(chunk) for chunk in chunks]
    retriever = get_weaviate_retriever()
    await asyncio.to_thread(retriever.add_documents, documents)
    return len(documents)
