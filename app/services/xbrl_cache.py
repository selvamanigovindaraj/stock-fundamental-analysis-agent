from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import edgar
from edgar.financials import Financials
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings
from app.models import FinancialStatements
from app.services.financial_sources import SourceUnavailableError, edgartools_source
from app.services.financial_sources.sec_edgar_source import fetch_companyfacts
from app.services.guardrails import sanitize_ticker

logger = logging.getLogger(__name__)

_CACHE_TTL = timedelta(hours=1)
_ANNUAL_FILINGS = 5
_QUARTERLY_FILINGS = 2

_CANONICAL_METRICS = {
    "Assets": "total_assets",
    "AssetsCurrent": "total_current_assets",
    "CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
    "CostOfGoodsAndServicesSold": "cost_of_revenue",
    "CostOfRevenue": "cost_of_revenue",
    "GrossProfit": "gross_profit",
    "InventoryNet": "inventory",
    "InterestExpense": "interest_expense",
    "Liabilities": "total_liabilities",
    "LiabilitiesCurrent": "total_current_liabilities",
    "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    "NetIncome": "net_income",
    "NetIncomeLoss": "net_income",
    "OperatingIncomeLoss": "operating_income",
    "PaymentsToAcquirePropertyPlantAndEquipment": "capital_expenditures",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "Revenues": "revenue",
    "RevenuesNetOfInterestExpense": "revenue",
    "SalesRevenueNet": "revenue",
    "StockholdersEquity": "total_equity",
}

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS companies (
        cik text PRIMARY KEY,
        ticker text NOT NULL UNIQUE,
        name text,
        last_checked_at timestamptz
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS filings (
        accession_no text PRIMARY KEY,
        cik text NOT NULL REFERENCES companies(cik),
        form_type text NOT NULL,
        filed_date date NOT NULL,
        period_end date,
        fiscal_year integer,
        fiscal_period text,
        filing_url text NOT NULL,
        normalized_statements jsonb,
        ingested_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS xbrl_facts (
        fact_key text PRIMARY KEY,
        accession_no text NOT NULL REFERENCES filings(accession_no) ON DELETE CASCADE,
        taxonomy text NOT NULL,
        concept text NOT NULL,
        canonical_metric text,
        unit text NOT NULL,
        value numeric NOT NULL,
        period_start date,
        period_end date NOT NULL,
        dimensions jsonb NOT NULL DEFAULT '{}',
        decimals integer,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS filings_company_period_idx ON filings (cik, period_end DESC)",
    """
    CREATE INDEX IF NOT EXISTS xbrl_facts_metric_period_idx
    ON xbrl_facts (canonical_metric, period_end DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS xbrl_facts_concept_period_idx
    ON xbrl_facts (concept, period_end DESC)
    """,
    "CREATE INDEX IF NOT EXISTS xbrl_facts_filing_idx ON xbrl_facts (accession_no)",
)

_pool: AsyncConnectionPool[Any] | None = None


@dataclass(frozen=True)
class _Filing:
    accession_no: str
    form_type: str
    filed_date: date
    period_end: date | None
    fiscal_year: int | None
    fiscal_period: str | None
    filing_url: str
    normalized_statements: dict[str, Any] | None = None


@dataclass(frozen=True)
class _Fact:
    accession_no: str
    taxonomy: str
    concept: str
    unit: str
    value: Decimal
    period_start: date | None
    period_end: date
    dimensions: dict[str, str]
    decimals: int | None

    @property
    def key(self) -> str:
        identity = json.dumps(
            [
                self.accession_no,
                self.taxonomy,
                self.concept,
                self.unit,
                str(self.period_start or ""),
                str(self.period_end),
                self.dimensions,
            ],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(identity.encode()).hexdigest()


@dataclass(frozen=True)
class _RefreshData:
    cik: str
    payload: dict[str, Any]
    companyfacts_filings: list[_Filing]
    companyfacts: list[_Fact]
    detailed_filings: list[_Filing]
    dimensional_facts: list[_Fact]


async def setup(pool: AsyncConnectionPool[Any]) -> None:
    """Create the cache schema idempotently and register the shared application pool."""
    global _pool
    async with pool.connection() as connection:
        async with connection.transaction():
            for statement in _SCHEMA:
                await connection.execute(statement)
    _pool = pool


def _date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _decimals(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _concept_parts(raw_concept: str) -> tuple[str, str]:
    separator = ":" if ":" in raw_concept else "_"
    taxonomy, _, concept = raw_concept.partition(separator)
    return taxonomy, concept or taxonomy


def _fact(
    *,
    accession_no: str,
    taxonomy: str,
    concept: str,
    unit: str,
    value: object,
    period_start: object,
    period_end: object,
    dimensions: dict[str, str] | None = None,
    decimals: object = None,
) -> _Fact | None:
    numeric_value = _decimal(value)
    end = _date(period_end)
    if numeric_value is None or end is None:
        return None
    return _Fact(
        accession_no=accession_no,
        taxonomy=taxonomy,
        concept=concept,
        unit=unit,
        value=numeric_value,
        period_start=_date(period_start),
        period_end=end,
        dimensions=dimensions or {},
        decimals=_decimals(decimals),
    )


def _companyfact_values(
    payload: dict[str, Any],
) -> Iterator[tuple[str, str, str, dict[str, Any]]]:
    """Yield flattened Company Facts values from the SEC's taxonomy/concept/unit nesting."""
    for taxonomy, concepts in payload.get("facts", {}).items():
        for concept, concept_data in concepts.items():
            for unit, values in concept_data.get("units", {}).items():
                for value in values:
                    yield taxonomy, concept, unit, value


def _companyfacts_rows(cik: str, payload: dict[str, Any]) -> tuple[list[_Filing], list[_Fact]]:
    filings: dict[str, _Filing] = {}
    facts: list[_Fact] = []
    for taxonomy, concept, unit, value in _companyfact_values(payload):
        accession_no = str(value.get("accn", ""))
        filed_date = _date(value.get("filed"))
        period_end = _date(value.get("end"))
        if not accession_no or filed_date is None or period_end is None:
            continue
        existing = filings.get(accession_no)
        if existing is None or existing.period_end is None or period_end > existing.period_end:
            filings[accession_no] = _Filing(
                accession_no=accession_no,
                form_type=str(value.get("form", "unknown")),
                filed_date=filed_date,
                period_end=period_end,
                fiscal_year=value.get("fy") if isinstance(value.get("fy"), int) else None,
                fiscal_period=str(value["fp"]) if value.get("fp") else None,
                filing_url=(
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                    f"{accession_no}-index.html"
                ),
            )
        parsed = _fact(
            accession_no=accession_no,
            taxonomy=taxonomy,
            concept=concept,
            unit=unit,
            value=value.get("val"),
            period_start=value.get("start"),
            period_end=value.get("end"),
            decimals=value.get("decimals"),
        )
        if parsed is not None:
            facts.append(parsed)
    return list(filings.values()), facts


def _normalized_snapshot(ticker: str, filing: Any, xbrl: Any) -> dict[str, Any] | None:
    if filing.form != "10-K":
        return None
    financials = Financials(xbrl)
    if financials is None:
        return None
    try:
        return edgartools_source.normalize_financials(ticker, financials).model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 - one malformed filing must not abort the batch
        logger.warning(
            "failed to normalize %s filing %s: %s", ticker, filing.accession_no, exc
        )
        return None


def _dimensional_facts(accession_no: str, raw_facts: list[dict[str, Any]]) -> list[_Fact]:
    facts: list[_Fact] = []
    for raw in raw_facts:
        dimensions = {
            key.removeprefix("dim_"): str(member)
            for key, member in raw.items()
            if key.startswith("dim_")
        }
        if not dimensions:
            continue
        raw_concept = raw.get("concept")
        if not raw_concept:
            continue
        taxonomy, concept = _concept_parts(str(raw_concept))
        parsed = _fact(
            accession_no=accession_no,
            taxonomy=taxonomy,
            concept=concept,
            unit=str(raw.get("currency") or raw.get("unit_ref") or "pure"),
            value=raw.get("value"),
            period_start=raw.get("period_start"),
            period_end=raw.get("period_end") or raw.get("period_instant"),
            dimensions=dimensions,
            decimals=raw.get("decimals"),
        )
        if parsed is not None:
            facts.append(parsed)
    return facts


def _parse_edgar_filing(ticker: str, filing: Any) -> tuple[_Filing, list[_Fact]] | None:
    xbrl = filing.xbrl()
    filed_date = _date(filing.filing_date)
    if xbrl is None or filed_date is None:
        return None
    accession_no = str(filing.accession_no)
    record = _Filing(
        accession_no=accession_no,
        form_type=str(filing.form),
        filed_date=filed_date,
        period_end=_date(filing.period_of_report),
        fiscal_year=None,
        fiscal_period="FY" if filing.form == "10-K" else None,
        filing_url=str(filing.filing_url),
        normalized_statements=_normalized_snapshot(ticker, filing, xbrl),
    )
    return record, _dimensional_facts(accession_no, xbrl.facts.get_facts())


def _selected_edgar_filings(ticker: str) -> tuple[list[_Filing], list[_Fact]]:
    edgar.set_identity(
        get_settings().sec_edgar_user_agent or "stock-fundamental-analyser research@example.com"
    )
    company = edgar.Company(ticker)
    selected = [
        *company.get_filings(form="10-K").head(_ANNUAL_FILINGS),
        *company.get_filings(form="10-Q").head(_QUARTERLY_FILINGS),
    ]
    filings: list[_Filing] = []
    facts: list[_Fact] = []
    for filing in selected:
        parsed = _parse_edgar_filing(ticker, filing)
        if parsed is None:
            continue
        record, filing_facts = parsed
        filings.append(record)
        facts.extend(filing_facts)
    return filings, facts


async def _cached(
    connection: Any, ticker: str, checked_after: datetime | None = None
) -> FinancialStatements | None:
    freshness = "AND c.last_checked_at >= %s" if checked_after else ""
    params = (ticker, checked_after) if checked_after else (ticker,)
    row = await (
        await connection.execute(
            f"""
            SELECT f.normalized_statements
            FROM companies c
            JOIN filings f ON f.cik = c.cik
            WHERE c.ticker = %s AND f.form_type = '10-K'
              AND f.normalized_statements IS NOT NULL {freshness}
            ORDER BY f.period_end DESC, f.filed_date DESC
            LIMIT 1
            """,
            params,
        )
    ).fetchone()
    if row is None:
        return None
    try:
        return FinancialStatements.model_validate(row["normalized_statements"])
    except ValueError:
        logger.warning("invalid cached FinancialStatements for %s; refreshing", ticker)
        return None


async def _upsert_filings(connection: Any, cik: str, filings: list[_Filing]) -> None:
    async with connection.cursor() as cursor:
        await cursor.executemany(
            """
            INSERT INTO filings (
                accession_no, cik, form_type, filed_date, period_end, fiscal_year,
                fiscal_period, filing_url, normalized_statements
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (accession_no) DO UPDATE SET
                form_type = EXCLUDED.form_type,
                filed_date = EXCLUDED.filed_date,
                period_end = EXCLUDED.period_end,
                fiscal_year = COALESCE(EXCLUDED.fiscal_year, filings.fiscal_year),
                fiscal_period = COALESCE(EXCLUDED.fiscal_period, filings.fiscal_period),
                filing_url = EXCLUDED.filing_url,
                normalized_statements = COALESCE(
                    EXCLUDED.normalized_statements, filings.normalized_statements
                ),
                ingested_at = now()
            """,
            [
                (
                    filing.accession_no,
                    cik,
                    filing.form_type,
                    filing.filed_date,
                    filing.period_end,
                    filing.fiscal_year,
                    filing.fiscal_period,
                    filing.filing_url,
                    Jsonb(filing.normalized_statements) if filing.normalized_statements else None,
                )
                for filing in filings
            ],
        )


async def _upsert_facts(connection: Any, facts: list[_Fact]) -> None:
    async with connection.cursor() as cursor:
        await cursor.executemany(
            """
            INSERT INTO xbrl_facts (
                fact_key, accession_no, taxonomy, concept, canonical_metric, unit,
                value, period_start, period_end, dimensions, decimals
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fact_key) DO UPDATE SET
                value = EXCLUDED.value,
                decimals = EXCLUDED.decimals
            """,
            [
                (
                    fact.key,
                    fact.accession_no,
                    fact.taxonomy,
                    fact.concept,
                    _CANONICAL_METRICS.get(fact.concept),
                    fact.unit,
                    fact.value,
                    fact.period_start,
                    fact.period_end,
                    Jsonb(fact.dimensions),
                    fact.decimals,
                )
                for fact in facts
            ],
        )


async def _download_refresh_data(ticker: str) -> _RefreshData:
    cik, payload = await fetch_companyfacts(ticker)
    companyfacts_filings, companyfacts = _companyfacts_rows(cik, payload)
    detailed_filings, dimensional_facts = await asyncio.to_thread(
        _selected_edgar_filings, ticker
    )
    return _RefreshData(
        cik=cik,
        payload=payload,
        companyfacts_filings=companyfacts_filings,
        companyfacts=companyfacts,
        detailed_filings=detailed_filings,
        dimensional_facts=dimensional_facts,
    )


async def _write_refresh(
    connection: Any, ticker: str, refresh: _RefreshData
) -> FinancialStatements:
    cik = refresh.cik
    await connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (cik,))
    cached = await _cached(connection, ticker, datetime.now(timezone.utc) - _CACHE_TTL)
    if cached is not None:
        return cached

    await connection.execute(
        """
        INSERT INTO companies (cik, ticker, name)
        VALUES (%s, %s, %s)
        ON CONFLICT (cik) DO UPDATE SET ticker = EXCLUDED.ticker, name = EXCLUDED.name
        """,
        (cik, ticker, refresh.payload.get("entityName")),
    )
    await _upsert_filings(
        connection,
        cik,
        [*refresh.companyfacts_filings, *refresh.detailed_filings],
    )
    await _upsert_facts(connection, [*refresh.companyfacts, *refresh.dimensional_facts])
    await connection.execute(
        "UPDATE companies SET last_checked_at = now() WHERE cik = %s", (cik,)
    )
    cached = await _cached(connection, ticker)
    if cached is None:
        raise SourceUnavailableError(f"Edgar cache produced no usable 10-K snapshot for {ticker}")
    return cached


async def fetch_financials(ticker: str) -> FinancialStatements:
    """Return fresh cached SEC statements, refreshing five 10-Ks and two 10-Qs on demand."""
    ticker = sanitize_ticker(ticker)
    if _pool is None:
        raise SourceUnavailableError("XBRL cache has not been initialized")
    async with _pool.connection() as connection:
        cached = await _cached(connection, ticker, datetime.now(timezone.utc) - _CACHE_TTL)
        if cached is not None:
            return cached
        stale = await _cached(connection, ticker)

    try:
        refresh = await _download_refresh_data(ticker)
    except Exception as exc:  # noqa: BLE001 - stale cache is the availability boundary
        if stale is not None:
            logger.warning("SEC fetch failed for %s; serving stale cache: %s", ticker, exc)
            return stale
        if isinstance(exc, SourceUnavailableError):
            raise
        raise SourceUnavailableError(f"Edgar fetch failed for {ticker}: {exc}") from exc

    async with _pool.connection() as connection:
        try:
            async with connection.transaction():
                return await _write_refresh(connection, ticker, refresh)
        except Exception as exc:  # noqa: BLE001 - stale cache is the availability boundary
            if stale is not None:
                logger.warning("SEC cache write failed for %s; serving stale cache: %s", ticker, exc)
                return stale
            if isinstance(exc, SourceUnavailableError):
                raise
            raise SourceUnavailableError(f"Edgar cache write failed for {ticker}: {exc}") from exc
