from __future__ import annotations

import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models import Chunk, FilingDocument

_CHUNK_SIZE = 1200
_CHUNK_OVERLAP = 150

# SEC-rendered filing text embeds a recurring page-footer inline, e.g.
# "Apple Inc. | 2025 Form 10-K | 21" -- verified live: left in place, this creates a
# near-empty chunk (just a section header + page number) that can outrank substantive
# content in semantic search for some queries. Stripped before chunking so boundaries
# stay anchored on real content instead of page breaks.
_PAGE_FOOTER_RE = re.compile(r"\n?[^\n|]{1,80}\|\s*\d{4}\s*Form\s*10-[KQ]\s*\|\s*\d+\n?")

# 10-Q Risk Factors sections are frequently just "no material changes from our most
# recent 10-K" boilerplate -- content-free and short. Skipping avoids polluting retrieval
# with a chunk that superficially matches many unrelated queries.
MIN_SECTION_LENGTH = 200

_splitter = RecursiveCharacterTextSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP)


def chunk_documents(documents: list[FilingDocument]) -> list[Chunk]:
    """Split each FilingDocument's section text into overlapping chunks, propagating metadata."""
    chunks: list[Chunk] = []
    for document in documents:
        if len(document.text) < MIN_SECTION_LENGTH:
            continue
        cleaned_text = _PAGE_FOOTER_RE.sub("\n", document.text)
        for index, text in enumerate(_splitter.split_text(cleaned_text)):
            chunks.append(
                Chunk(
                    text=text,
                    ticker=document.ticker,
                    form_type=document.form_type,
                    period=document.period,
                    section=document.section,
                    accession_no=document.accession_no,
                    filing_url=document.filing_url,
                    chunk_index=index,
                )
            )
    return chunks
