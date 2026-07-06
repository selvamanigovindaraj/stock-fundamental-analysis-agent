from __future__ import annotations


class SourceUnavailableError(Exception):
    """Raised by a financial-data source adapter when it cannot produce a complete
    FinancialStatements for a ticker (network failure, missing/partial data, malformed
    response). Signals the ingestion fallback chain to try the next source."""
