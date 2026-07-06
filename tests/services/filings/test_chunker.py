from __future__ import annotations

from app.models import FilingDocument
from app.services.filings.chunker import MIN_SECTION_LENGTH, chunk_documents

_BASE_KWARGS = dict(
    ticker="AAPL",
    form_type="10-K",
    period="2024-09-30",
    accession_no="0000320193-24-000123",
    filing_url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
    section="risk_factors",
)


def test_chunk_documents_respects_size_and_overlap() -> None:
    text = "A" * 3000
    doc = FilingDocument(text=text, **_BASE_KWARGS)

    chunks = chunk_documents([doc])

    assert len(chunks) > 1
    assert all(len(c.text) <= 1200 for c in chunks)
    # consecutive chunks overlap by roughly chunk_overlap characters
    assert chunks[0].text[-150:] in chunks[1].text


def test_chunk_documents_propagates_metadata_and_index() -> None:
    text = "B" * 3000
    doc = FilingDocument(text=text, **_BASE_KWARGS)

    chunks = chunk_documents([doc])

    for i, chunk in enumerate(chunks):
        assert chunk.ticker == "AAPL"
        assert chunk.form_type == "10-K"
        assert chunk.period == "2024-09-30"
        assert chunk.section == "risk_factors"
        assert chunk.accession_no == "0000320193-24-000123"
        assert chunk.filing_url == _BASE_KWARGS["filing_url"]
        assert chunk.chunk_index == i


def test_chunk_documents_skips_boilerplate_short_sections() -> None:
    """A 10-Q's Part II Item 1A is frequently just "no material changes from our most
    recent 10-K" -- content-free and short. Skipping avoids polluting retrieval with a
    chunk that superficially matches many unrelated queries."""
    short_doc = FilingDocument(
        text="There have been no material changes to our risk factors.", **_BASE_KWARGS
    )

    chunks = chunk_documents([short_doc])

    assert chunks == []


def test_min_section_length_is_a_real_threshold() -> None:
    assert MIN_SECTION_LENGTH > 0


def test_chunk_documents_strips_page_footer_noise() -> None:
    """SEC-rendered filing text has recurring page-footer noise ("Apple Inc. | 2025 Form
    10-K | 21") embedded inline. Verified live: this creates a near-empty chunk (just a
    section header + page number) that can outrank substantive content in semantic search
    for some queries -- stripping it keeps chunk boundaries anchored on real content."""
    text = (
        "Tariffs and Other Measures\n\n"
        "Apple Inc. | 2025 Form 10-K | 21\n\n"
        "Beginning in the second quarter of 2025, new U.S. Tariffs were announced. " * 10
    )
    doc = FilingDocument(text=text, **_BASE_KWARGS)

    chunks = chunk_documents([doc])

    assert all("Apple Inc. | 2025 Form 10-K | 21" not in c.text for c in chunks)
    assert any("Tariffs and Other Measures" in c.text for c in chunks)
