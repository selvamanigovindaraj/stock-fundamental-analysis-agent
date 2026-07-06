from __future__ import annotations

import asyncio
import math
import time
from typing import Any

import httpx

from app.config import get_settings
from app.models import BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement
from app.services.financial_sources import SourceUnavailableError

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_RATE_LIMIT_PER_SEC = 10

_DEBT_TAGS = ("LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings")


class _RateLimiter:
    """Module-level, lock-guarded sliding-window limiter capping requests at N per second.

    ponytail: single consumer today; extract to a shared module if a second rate-limited API appears.
    """

    def __init__(self, max_per_second: int) -> None:
        self._max_per_second = max_per_second
        self._lock = asyncio.Lock()
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < 1.0]
            if len(self._timestamps) >= self._max_per_second:
                sleep_for = 1.0 - (now - self._timestamps[0])
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < 1.0]
            self._timestamps.append(now)


_rate_limiter = _RateLimiter(_RATE_LIMIT_PER_SEC)
_client: httpx.AsyncClient | None = None
_cik_cache: dict[str, str] = {}


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(headers={"User-Agent": get_settings().sec_edgar_user_agent})
    return _client


async def _get_json(client: httpx.AsyncClient, url: str) -> Any:
    await _rate_limiter.acquire()
    response = await client.get(url)
    if response.status_code != 200:
        raise SourceUnavailableError(f"SEC EDGAR request to {url} failed: {response.status_code}")
    return response.json()


async def _lookup_cik(client: httpx.AsyncClient, ticker: str) -> str:
    normalized = ticker.upper().replace(".", "-")
    if not _cik_cache:
        payload = await _get_json(client, _TICKERS_URL)
        for entry in payload.values():
            _cik_cache[str(entry["ticker"]).upper()] = str(entry["cik_str"]).zfill(10)
    if normalized not in _cik_cache:
        raise SourceUnavailableError(f"ticker not found in SEC CIK map: {ticker}")
    return _cik_cache[normalized]


def _dedupe_by_period(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse facts to one per fiscal period-end, keeping the latest-filed value
    (a restated period gets a new accession number but the same `end` date)."""
    latest: dict[str, dict[str, Any]] = {}
    for fact in facts:
        end = fact["end"]
        if end not in latest or fact["filed"] > latest[end]["filed"]:
            latest[end] = fact
    return list(latest.values())


def _find_tag_value(usgaap: dict[str, Any], tag_names: tuple[str, ...]) -> float | None:
    for name in tag_names:
        concept = usgaap.get(name)
        if not concept:
            continue
        deduped = _dedupe_by_period(concept.get("units", {}).get("USD", []))
        if deduped:
            return float(max(deduped, key=lambda f: f["end"])["val"])
    return None


def _required_tag_value(usgaap: dict[str, Any], tag_names: tuple[str, ...]) -> float:
    value = _find_tag_value(usgaap, tag_names)
    if value is None:
        raise SourceUnavailableError(f"SEC EDGAR companyfacts missing tags: {tag_names}")
    return value


def _optional_tag_value(usgaap: dict[str, Any], tag_names: tuple[str, ...], *, default: float = 0.0) -> float:
    value = _find_tag_value(usgaap, tag_names)
    return default if value is None else value


def _period_end(usgaap: dict[str, Any], tag_name: str) -> str:
    deduped = _dedupe_by_period(usgaap.get(tag_name, {}).get("units", {}).get("USD", []))
    if not deduped:
        raise SourceUnavailableError(f"SEC EDGAR companyfacts missing tag: {tag_name}")
    return str(max(deduped, key=lambda f: f["end"])["end"])


async def fetch_financials(ticker: str) -> FinancialStatements:
    """Fetch and normalize income statement, balance sheet, and cash flow via the direct
    SEC EDGAR companyfacts API."""
    client = _get_client()
    try:
        cik = await _lookup_cik(client, ticker)
        payload = await _get_json(client, _COMPANYFACTS_URL.format(cik=cik))
    except SourceUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001 - any vendor failure means "try the next source"
        raise SourceUnavailableError(f"SEC EDGAR request failed: {exc}") from exc

    usgaap = payload.get("facts", {}).get("us-gaap", {})

    def required(*names: str) -> float:
        return _required_tag_value(usgaap, names)

    def optional(*names: str, default: float = 0.0) -> float:
        return _optional_tag_value(usgaap, names, default=default)

    period_end = _period_end(usgaap, "Assets")
    total_debt = sum(_optional_tag_value(usgaap, (name,)) for name in _DEBT_TAGS)

    return FinancialStatements(
        ticker=ticker,
        source="sec_edgar",
        is_gaap=True,
        income_statement=IncomeStatement(
            period_end=period_end,
            total_revenue=required("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"),
            # Banks (e.g. JPM) have no CostOfRevenue/GrossProfit/OperatingIncomeLoss tag at all
            # (net interest income model instead) — NaN means "not applicable", not 0.
            cost_of_revenue=optional("CostOfRevenue", "CostOfGoodsAndServicesSold", default=math.nan),
            gross_profit=optional("GrossProfit", default=math.nan),
            operating_income=optional("OperatingIncomeLoss", default=math.nan),
            interest_expense=optional("InterestExpense"),
            net_income=required("NetIncomeLoss"),
        ),
        balance_sheet=BalanceSheet(
            period_end=period_end,
            # Banks use an unclassified balance sheet (no AssetsCurrent/LiabilitiesCurrent
            # tags) — 0.0 is safe because RatioEngine's zero-denominator check already
            # converts ratios dividing by total_current_liabilities to NaN.
            total_current_assets=optional("AssetsCurrent"),
            inventory=optional("InventoryNet"),
            total_current_liabilities=optional("LiabilitiesCurrent"),
            total_assets=required("Assets"),
            total_liabilities=required("Liabilities"),
            total_debt=total_debt,
            total_equity=required("StockholdersEquity"),
            cash_and_equivalents=optional("CashAndCashEquivalentsAtCarryingValue"),
        ),
        cash_flow=CashFlowStatement(
            period_end=period_end,
            operating_cash_flow=required("NetCashProvidedByUsedInOperatingActivities"),
            capital_expenditures=optional("PaymentsToAcquirePropertyPlantAndEquipment"),
        ),
    )
