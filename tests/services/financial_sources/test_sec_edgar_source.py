from __future__ import annotations

import asyncio
import math

import httpx
import pytest

from app.services.financial_sources import SourceUnavailableError
from app.services.financial_sources import sec_edgar_source


class _FakeClock:
    def __init__(self) -> None:
        self.time = 0.0

    def monotonic(self) -> float:
        return self.time

    async def sleep(self, duration: float) -> None:
        self.time += duration


def _tickers_payload() -> dict[str, object]:
    return {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 1652044, "ticker": "BRK-B", "title": "Berkshire Hathaway"},
        "2": {"cik_str": 19617, "ticker": "JPM", "title": "JPMorgan Chase & Co."},
    }


def _companyfacts_payload(*, missing_tags: list[str] | None = None) -> dict[str, object]:
    def usd(*facts: dict[str, object]) -> dict[str, object]:
        return {"units": {"USD": list(facts)}}

    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": usd({"end": "2025-09-27", "val": 416_161e6, "accn": "a1", "filed": "2025-11-01"}),
                "CostOfRevenue": usd(
                    {"end": "2025-09-27", "val": 220_960e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "GrossProfit": usd(
                    {"end": "2025-09-27", "val": 195_201e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "OperatingIncomeLoss": usd(
                    {"end": "2025-09-27", "val": 133_050e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "InterestExpense": usd(
                    {"end": "2025-09-27", "val": 3_933e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "NetIncomeLoss": usd(
                    {"end": "2025-09-27", "val": 112_010e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "AssetsCurrent": usd(
                    {"end": "2025-09-27", "val": 147_957e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "InventoryNet": usd(
                    {"end": "2025-09-27", "val": 5_718e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "LiabilitiesCurrent": usd(
                    {"end": "2025-09-27", "val": 165_631e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "Assets": usd({"end": "2025-09-27", "val": 359_241e6, "accn": "a1", "filed": "2025-11-01"}),
                "Liabilities": usd(
                    {"end": "2025-09-27", "val": 285_508e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "StockholdersEquity": usd(
                    {"end": "2025-09-27", "val": 73_733e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "CashAndCashEquivalentsAtCarryingValue": usd(
                    {"end": "2025-09-27", "val": 35_934e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "NetCashProvidedByUsedInOperatingActivities": usd(
                    {"end": "2025-09-27", "val": 111_482e6, "accn": "a1", "filed": "2025-11-01"}
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd(
                    {"end": "2025-09-27", "val": 12_715e6, "accn": "a1", "filed": "2025-11-01"}
                ),
            }
        }
    }
    for tag in missing_tags or []:
        payload["facts"]["us-gaap"].pop(tag, None)
    return payload


def _install_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    user_agent: str = "Test/1.0 a@b.com",
    missing_tags: list[str] | None = None,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == user_agent
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=_tickers_payload())
        if "companyfacts" in request.url.path:
            return httpx.Response(200, json=_companyfacts_payload(missing_tags=missing_tags))
        return httpx.Response(404)

    sec_edgar_source._client = httpx.AsyncClient(
        headers={"User-Agent": user_agent}, transport=httpx.MockTransport(handler)
    )
    sec_edgar_source._cik_cache.clear()


@pytest.fixture(autouse=True)
def _reset_module_state() -> None:
    sec_edgar_source._cik_cache.clear()
    sec_edgar_source._client = None
    yield
    sec_edgar_source._cik_cache.clear()
    sec_edgar_source._client = None


def test_dedupe_by_period_keeps_latest_filed_per_period() -> None:
    facts = [
        {"end": "2008-09-27", "val": 39_572_000_000, "accn": "a", "filed": "2009-07-22"},
        {"end": "2008-09-27", "val": 39_572_000_000, "accn": "b", "filed": "2009-10-27"},
        {"end": "2008-09-27", "val": 36_171_000_000, "accn": "c", "filed": "2010-01-25"},  # restated
        {"end": "2009-09-26", "val": 42_905_000_000, "accn": "d", "filed": "2010-10-27"},
    ]

    deduped = sec_edgar_source._dedupe_by_period(facts)

    by_period = {fact["end"]: fact for fact in deduped}
    assert len(deduped) == 2
    assert by_period["2008-09-27"]["val"] == 36_171_000_000  # the restated value wins
    assert by_period["2009-09-26"]["val"] == 42_905_000_000


@pytest.mark.asyncio
async def test_rate_limiter_throttles_concurrent_callers(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(sec_edgar_source.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(sec_edgar_source.asyncio, "sleep", clock.sleep)

    limiter = sec_edgar_source._RateLimiter(max_per_second=10)
    await asyncio.gather(*(limiter.acquire() for _ in range(20)))

    # A sliding window only remembers the last second, so this doesn't grow unbounded to 20 —
    # it never exceeds the cap, which is the actual throttling invariant.
    assert len(limiter._timestamps) <= 10
    assert clock.time > 0  # throttling engaged at least once for the 11th+ request


@pytest.mark.asyncio
async def test_lookup_cik_normalizes_dotted_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock_transport(monkeypatch)
    client = sec_edgar_source._get_client()

    cik = await sec_edgar_source._lookup_cik(client, "BRK.B")

    assert cik == "0001652044"


@pytest.mark.asyncio
async def test_lookup_cik_raises_on_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock_transport(monkeypatch)
    client = sec_edgar_source._get_client()

    with pytest.raises(SourceUnavailableError):
        await sec_edgar_source._lookup_cik(client, "NOPE")


@pytest.mark.asyncio
async def test_fetch_financials_sends_configured_user_agent_and_normalizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sec_edgar_source.get_settings(), "sec_edgar_user_agent", "Test/1.0 a@b.com")
    _install_mock_transport(monkeypatch, user_agent="Test/1.0 a@b.com")

    result = await sec_edgar_source.fetch_financials("AAPL")

    assert result.ticker == "AAPL"
    assert result.source == "sec_edgar"
    assert result.is_gaap is True
    assert result.income_statement.total_revenue == pytest.approx(416_161e6)
    assert result.income_statement.interest_expense == pytest.approx(3_933e6)
    assert result.balance_sheet.total_current_assets == pytest.approx(147_957e6)
    assert result.cash_flow.operating_cash_flow == pytest.approx(111_482e6)
    assert result.cash_flow.capital_expenditures == pytest.approx(12_715e6)


@pytest.mark.asyncio
async def test_fetch_financials_handles_bank_shaped_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    """Banks (e.g. JPM) have no CostOfRevenue/GrossProfit/OperatingIncomeLoss tag and no
    AssetsCurrent/LiabilitiesCurrent tags in SEC XBRL at all — missing income fields must come
    back as NaN ("not applicable"), missing balance fields safely default to 0.0."""
    monkeypatch.setattr(sec_edgar_source.get_settings(), "sec_edgar_user_agent", "Test/1.0 a@b.com")
    _install_mock_transport(
        monkeypatch,
        user_agent="Test/1.0 a@b.com",
        missing_tags=[
            "CostOfRevenue",
            "GrossProfit",
            "OperatingIncomeLoss",
            "AssetsCurrent",
            "LiabilitiesCurrent",
        ],
    )

    result = await sec_edgar_source.fetch_financials("JPM")

    assert math.isnan(result.income_statement.cost_of_revenue)
    assert math.isnan(result.income_statement.gross_profit)
    assert math.isnan(result.income_statement.operating_income)
    assert result.balance_sheet.total_current_assets == 0.0
    assert result.balance_sheet.total_current_liabilities == 0.0
    assert result.income_statement.total_revenue == pytest.approx(416_161e6)


@pytest.mark.asyncio
async def test_fetch_financials_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=_tickers_payload())
        return httpx.Response(404)

    sec_edgar_source._client = httpx.AsyncClient(
        headers={"User-Agent": "Test/1.0 a@b.com"}, transport=httpx.MockTransport(handler)
    )
    sec_edgar_source._cik_cache.clear()

    with pytest.raises(SourceUnavailableError):
        await sec_edgar_source.fetch_financials("AAPL")
