from __future__ import annotations

import pytest

from app.services.filings import downloader
from app.services.financial_sources import SourceUnavailableError

_MDNA_TEXT = "Management discussion. " * 20
_RISK_TEXT = "Risk factors discussion. " * 20
_BOILERPLATE = "There have been no material changes to our risk factors."


class _FakeTenK:
    def __init__(self, *, mdna: str = _MDNA_TEXT, risk_factors: str = _RISK_TEXT) -> None:
        self.management_discussion = mdna
        self.risk_factors = risk_factors


class _FakeTenQ:
    def __init__(self, *, mdna: str = _MDNA_TEXT, risk_factors: str = _BOILERPLATE) -> None:
        self._items = {"Item 2": mdna, "Part II, Item 1A": risk_factors}

    def __getitem__(self, key: str) -> str:
        return self._items[key]


def _make_fake_filing(form: str, *, accession_no: str, period: str, obj: object) -> object:
    class FakeFiling:
        period_of_report = period
        filing_url = f"https://www.sec.gov/Archives/edgar/data/example/{accession_no}.htm"

        def obj(self) -> object:
            return obj

    filing = FakeFiling()
    filing.accession_no = accession_no
    return filing


def _make_fake_company(*, ten_k_filings: list[object], ten_q_filings: list[object]) -> object:
    class FakeFilingsList(list):
        def head(self, n: int) -> list[object]:
            return self[:n]

    class FakeCompany:
        def get_filings(self, form: str) -> FakeFilingsList:
            return FakeFilingsList(ten_k_filings if form == "10-K" else ten_q_filings)

    return FakeCompany()


@pytest.mark.asyncio
async def test_fetch_recent_filings_extracts_both_forms_and_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ten_k = _make_fake_filing(
        "10-K", accession_no="0000320193-24-000123", period="2024-09-28", obj=_FakeTenK()
    )
    ten_q = _make_fake_filing(
        "10-Q", accession_no="0000320193-25-000001", period="2025-03-29", obj=_FakeTenQ(risk_factors=_RISK_TEXT)
    )
    monkeypatch.setattr(
        downloader.edgar,
        "Company",
        lambda ticker: _make_fake_company(ten_k_filings=[ten_k], ten_q_filings=[ten_q]),
    )
    monkeypatch.setattr(downloader.edgar, "set_identity", lambda identity: None)

    documents = await downloader.fetch_recent_filings("AAPL")

    assert len(documents) == 4  # 2 sections x (1 10-K + 1 10-Q)
    by_key = {(d.form_type, d.section): d for d in documents}
    assert by_key[("10-K", "mdna")].text == _MDNA_TEXT
    assert by_key[("10-K", "risk_factors")].text == _RISK_TEXT
    assert by_key[("10-Q", "mdna")].text == _MDNA_TEXT
    assert by_key[("10-Q", "risk_factors")].text == _RISK_TEXT
    assert by_key[("10-K", "mdna")].ticker == "AAPL"
    assert by_key[("10-K", "mdna")].accession_no == "0000320193-24-000123"
    assert by_key[("10-K", "mdna")].period == "2024-09-28"


@pytest.mark.asyncio
async def test_fetch_recent_filings_skips_empty_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Some filings genuinely have no text for a section (e.g. malformed/very old filings) --
    the downloader only guards against emptiness; the boilerplate-length heuristic (a
    real-but-content-free section like a 10-Q's "no material changes" filler) is chunker.py's
    concern, not the downloader's -- see test_chunker.py."""
    ten_q = _make_fake_filing(
        "10-Q", accession_no="0000320193-25-000001", period="2025-03-29", obj=_FakeTenQ(risk_factors="")
    )
    monkeypatch.setattr(
        downloader.edgar,
        "Company",
        lambda ticker: _make_fake_company(ten_k_filings=[], ten_q_filings=[ten_q]),
    )
    monkeypatch.setattr(downloader.edgar, "set_identity", lambda identity: None)

    documents = await downloader.fetch_recent_filings("AAPL")

    sections = {d.section for d in documents}
    assert "risk_factors" not in sections
    assert "mdna" in sections


@pytest.mark.asyncio
async def test_fetch_recent_filings_tolerates_fewer_than_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recent IPO may have fewer than 2 historical 10-Ks -- must not assume exactly 2."""
    monkeypatch.setattr(
        downloader.edgar,
        "Company",
        lambda ticker: _make_fake_company(ten_k_filings=[], ten_q_filings=[]),
    )
    monkeypatch.setattr(downloader.edgar, "set_identity", lambda identity: None)

    documents = await downloader.fetch_recent_filings("NEWCO")

    assert documents == []


@pytest.mark.asyncio
async def test_fetch_recent_filings_raises_on_vendor_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_company(ticker: str) -> object:
        raise RuntimeError("edgar is down")

    monkeypatch.setattr(downloader.edgar, "Company", _raise_company)
    monkeypatch.setattr(downloader.edgar, "set_identity", lambda identity: None)

    with pytest.raises(SourceUnavailableError):
        await downloader.fetch_recent_filings("AAPL")
