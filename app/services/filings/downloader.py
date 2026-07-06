from __future__ import annotations

import asyncio
from typing import Any, Literal

import edgar

from app.config import get_settings
from app.models import FilingDocument
from app.services.financial_sources import SourceUnavailableError

_FORM_TYPES: tuple[Literal["10-K", "10-Q"], ...] = ("10-K", "10-Q")
_TEN_Q_ITEM_KEYS = {"mdna": "Item 2", "risk_factors": "Part II, Item 1A"}


async def fetch_recent_filings(ticker: str, *, count_per_form: int = 2) -> list[FilingDocument]:
    """Fetch the most recent `count_per_form` 10-K and 10-Q filings for `ticker` and
    extract their MD&A and Risk Factors sections. Tolerates fewer filings existing (e.g.
    a recent IPO) and skips boilerplate/empty sections."""

    def _fetch() -> list[FilingDocument]:
        edgar.set_identity(
            get_settings().sec_edgar_user_agent or "stock-fundamental-analyser research@example.com"
        )
        company = edgar.Company(ticker)
        documents: list[FilingDocument] = []
        for form_type in _FORM_TYPES:
            for filing in company.get_filings(form=form_type).head(count_per_form):
                documents.extend(_extract_sections(ticker, form_type, filing))
        return documents

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as exc:  # noqa: BLE001 - any vendor failure means "this ticker failed"
        raise SourceUnavailableError(f"filings download failed for {ticker}: {exc}") from exc


def _extract_sections(
    ticker: str, form_type: Literal["10-K", "10-Q"], filing: Any
) -> list[FilingDocument]:
    obj = filing.obj()
    if form_type == "10-K":
        section_texts = {"mdna": obj.management_discussion, "risk_factors": obj.risk_factors}
    else:
        section_texts = {key: _safe_item(obj, item) for key, item in _TEN_Q_ITEM_KEYS.items()}

    documents = []
    for section, text in section_texts.items():
        if text:
            documents.append(
                FilingDocument(
                    ticker=ticker,
                    form_type=form_type,
                    period=filing.period_of_report,
                    accession_no=filing.accession_no,
                    filing_url=filing.filing_url,
                    section=section,  # type: ignore[arg-type]
                    text=text,
                )
            )
    return documents


def _safe_item(obj: Any, item_key: str) -> str:
    try:
        return str(obj[item_key])
    except KeyError:
        return ""
