from __future__ import annotations

import math
import re
from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.models import AnalystReport, FundamentalRatios


class GuardrailViolation(ValueError):
    """Raised when untrusted input or generated output violates deterministic guardrails."""


_TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z])?$")
_NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?(?![-A-Za-z])")
_URL_RE = re.compile(r"https?://\S+")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NATURAL_DATE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_YEAR_MIN = 1900
_YEAR_MAX = 2100


def sanitize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not _TICKER_RE.fullmatch(normalized):
        raise GuardrailViolation(f"invalid ticker symbol: {ticker!r}")
    return normalized


def validate_api_bounds(*, days: int, max_results: int) -> None:
    if not 1 <= days <= 365:
        raise GuardrailViolation("days must be between 1 and 365")
    if not 1 <= max_results <= 50:
        raise GuardrailViolation("max_results must be between 1 and 50")


def validate_date_range(start: str, end: str) -> None:
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        raise GuardrailViolation("dates must use YYYY-MM-DD format") from exc
    if start_date > end_date:
        raise GuardrailViolation("start date must be on or before end date")


def _report_text(report: AnalystReport) -> str:
    parts: list[str] = [
        report.executive_summary,
        report.financial_health,
        report.valuation_assessment,
        *report.risk_factors,
        *report.key_themes,
    ]
    return "\n".join(parts)


def _ratio_numbers(ratios: FundamentalRatios) -> set[float]:
    values: set[float] = set()
    for value in ratios.model_dump().values():
        if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
            continue
        raw = float(value)
        for scaled in (raw, raw * 100, raw / 1_000_000, raw / 1_000_000_000):
            values.add(scaled)
    return values


def _supported(value: float, allowed: set[float]) -> bool:
    if value.is_integer() and _YEAR_MIN <= value <= _YEAR_MAX:
        return True
    return any(math.isclose(value, candidate, rel_tol=0.0, abs_tol=0.1) for candidate in allowed)


def find_unsupported_report_numbers(
    report: AnalystReport, ratios: FundamentalRatios | None
) -> list[str]:
    if ratios is None:
        return []
    allowed = _ratio_numbers(ratios)
    text = _NATURAL_DATE_RE.sub("", _DATE_RE.sub("", _URL_RE.sub("", _report_text(report))))
    unsupported: list[str] = []
    for match in _NUMBER_RE.finditer(text):
        token = match.group(0)
        value = float(token.rstrip("%").replace(",", ""))
        if not _supported(value, allowed):
            unsupported.append(token.rstrip("%"))
    return unsupported


def redact_unsupported_report_numbers(
    report: AnalystReport, ratios: FundamentalRatios | None
) -> AnalystReport:
    if ratios is None:
        return report
    allowed = _ratio_numbers(ratios)

    def redact_text(text: str) -> str:
        ignored_spans = [
            match.span()
            for pattern in (_NATURAL_DATE_RE, _DATE_RE, _URL_RE)
            for match in pattern.finditer(text)
        ]

        def replace(match: re.Match[str]) -> str:
            token = match.group(0)
            start, end = match.span()
            if any(istart <= start and end <= iend for istart, iend in ignored_spans):
                return token
            value = float(token.rstrip("%").replace(",", ""))
            return token if _supported(value, allowed) else "[unsupported figure removed]"

        return _NUMBER_RE.sub(replace, text)

    return report.model_copy(
        update={
            "executive_summary": redact_text(report.executive_summary),
            "financial_health": redact_text(report.financial_health),
            "valuation_assessment": redact_text(report.valuation_assessment),
            "risk_factors": [redact_text(item) for item in report.risk_factors],
            "key_themes": [redact_text(item) for item in report.key_themes],
        }
    )


@lru_cache(maxsize=1)
def _presidio_analyzer() -> Any:
    from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]

    return AnalyzerEngine()


def scan_report_pii(report: AnalystReport) -> list[str]:
    text = _report_text(report)
    try:
        findings = _presidio_analyzer().analyze(text=text, language="en")
        return [finding.entity_type for finding in findings if finding.entity_type != "PERSON"]
    except Exception:
        findings = []
        for label, pattern in {
            "EMAIL_ADDRESS": _EMAIL_RE,
            "PHONE_NUMBER": _PHONE_RE,
            "US_SSN": _SSN_RE,
        }.items():
            if pattern.search(text):
                findings.append(label)
        return findings


def validate_model(value: BaseModel) -> None:
    type(value).model_validate(value.model_dump())
