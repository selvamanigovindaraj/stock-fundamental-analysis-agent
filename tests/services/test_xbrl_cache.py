from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services import xbrl_cache


def _fact(dimensions: dict[str, str]) -> xbrl_cache._Fact:
    return xbrl_cache._Fact(
        accession_no="0001-25-000001",
        taxonomy="us-gaap",
        concept="Revenues",
        unit="USD",
        value=Decimal("100"),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        dimensions=dimensions,
        decimals=-6,
    )


def test_fact_key_is_stable_across_dimension_order() -> None:
    first = _fact({"ProductAxis": "ServicesMember", "GeographyAxis": "USMember"})
    second = _fact({"GeographyAxis": "USMember", "ProductAxis": "ServicesMember"})

    assert first.key == second.key


def test_companyfacts_rows_keep_complete_history_and_exact_values() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "accn": f"annual-{year}",
                                "form": "10-K",
                                "filed": f"{year + 1}-02-01",
                                "start": f"{year}-01-01",
                                "end": f"{year}-12-31",
                                "fy": year,
                                "fp": "FY",
                                "val": "12345678901234567890.12",
                            }
                            for year in range(2020, 2025)
                        ]
                    }
                }
            }
        }
    }

    filings, facts = xbrl_cache._companyfacts_rows("0000320193", payload)

    assert len(filings) == 5
    assert len(facts) == 5
    assert facts[0].value == Decimal("12345678901234567890.12")
    assert all(fact.taxonomy == "us-gaap" for fact in facts)
    assert all(fact.concept == "Revenues" for fact in facts)


def test_canonical_metric_preserves_bank_revenue_mapping() -> None:
    assert xbrl_cache._CANONICAL_METRICS["RevenuesNetOfInterestExpense"] == "revenue"


def test_detailed_extraction_selects_five_10ks_and_two_10qs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[tuple[str, int]] = []

    class FakeFacts:
        def get_facts(self) -> list[dict[str, object]]:
            return []

    class FakeXbrl:
        facts = FakeFacts()

    class FakeFiling:
        def __init__(self, form: str, index: int) -> None:
            self.form = form
            self.accession_no = f"{form}-{index}"
            self.filing_date = "2025-01-01"
            self.period_of_report = "2024-12-31"
            self.filing_url = f"https://example.test/{form}/{index}"

        def xbrl(self) -> FakeXbrl:
            return FakeXbrl()

    class FakeFilings:
        def __init__(self, form: str) -> None:
            self.form = form

        def head(self, count: int) -> list[FakeFiling]:
            requested.append((self.form, count))
            return [FakeFiling(self.form, index) for index in range(count)]

    class FakeCompany:
        def get_filings(self, *, form: str) -> FakeFilings:
            return FakeFilings(form)

    monkeypatch.setattr(xbrl_cache.edgar, "Company", lambda ticker: FakeCompany())
    monkeypatch.setattr(xbrl_cache.edgar, "set_identity", lambda identity: None)
    monkeypatch.setattr(xbrl_cache.Financials, "extract", lambda filing: None)

    filings, facts = xbrl_cache._selected_edgar_filings("AAPL")

    assert requested == [("10-K", 5), ("10-Q", 2)]
    assert len(filings) == 7
    assert facts == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("us-gaap:Assets", ("us-gaap", "Assets")),
        ("us-gaap_Assets", ("us-gaap", "Assets")),
        ("custom_RevenueByProduct", ("custom", "RevenueByProduct")),
    ],
)
def test_concept_parts_supports_edgar_namespace_shapes(
    raw: str, expected: tuple[str, str]
) -> None:
    assert xbrl_cache._concept_parts(raw) == expected


@pytest.mark.asyncio
async def test_bulk_fact_upsert_uses_async_cursor() -> None:
    calls: list[tuple[str, list[tuple[object, ...]]]] = []

    class FakeCursor:
        async def __aenter__(self) -> FakeCursor:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def executemany(
            self, statement: str, values: list[tuple[object, ...]]
        ) -> None:
            calls.append((statement, values))

    class FakeConnection:
        def cursor(self) -> FakeCursor:
            return FakeCursor()

    await xbrl_cache._upsert_facts(FakeConnection(), [_fact({})])

    assert len(calls) == 1
    assert calls[0][1][0][0] == _fact({}).key
