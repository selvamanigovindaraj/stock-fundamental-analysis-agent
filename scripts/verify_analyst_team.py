from __future__ import annotations

import asyncio
import os
import time

# Must be set before any `langgraph` import in this process, matching app/main.py's own
# bootstrap (see CLAUDE.md / GHSA-g48c-2wqr-h844).
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: E402

from app.agents.analyst_team_graph import init_analyst_team_graph, run_team_analysis  # noqa: E402
from app.agents.news_sentiment_graph import run_news_sentiment  # noqa: E402
from app.agents.report_writer_graph import run_report_writer  # noqa: E402
from app.agents.supervisor_graph import init_supervisor_graph, run_supervisor_analysis  # noqa: E402
from app.agents.valuation_graph import run_valuation  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import close_pool, open_pool  # noqa: E402
from app.services.financial_sources import SourceUnavailableError  # noqa: E402
from app.services.sector_benchmarks import fetch_sector_benchmark  # noqa: E402

TIME_BUDGET_SECONDS = 120.0

# 10 tickers across the 4 goal-named sectors (tech, healthcare, energy, financials) plus a
# couple more for variety. Not reused for the speedup measurement below (see SPEEDUP_TICKER)
# so a resumed/already-completed checkpoint thread can't skew that timing comparison.
TICKERS_BY_SECTOR: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT"],
    "Healthcare": ["JNJ", "UNH"],
    "Energy": ["XOM", "CVX"],
    "Financial Services": ["JPM", "BAC"],
    "Consumer Cyclical": ["AMZN", "TSLA"],
}
SPEEDUP_TICKER = "GOOGL"


async def _time_team_run(ticker: str) -> tuple[float, bool, str]:
    start = time.monotonic()
    try:
        result = await run_team_analysis(ticker)
        return time.monotonic() - start, result["report"] is not None, ""
    except Exception as exc:  # noqa: BLE001 - report every failure, don't abort the whole run
        return time.monotonic() - start, False, str(exc)


async def _time_sequential_baseline(ticker: str) -> float:
    """Times the *same total workload* as the fanned-out team run -- all 5 agents, just
    called one after another instead of fanning out financials+news. Must cover identical
    work to the parallel run for the speedup comparison to mean anything; an earlier version
    of this function only timed 2 of the 5 agents against the full 5-agent parallel run,
    making the "speedup" it reported meaningless (parallel looked slower only because it was
    doing 3x the work) -- caught via live verify-agent."""
    start = time.monotonic()
    try:
        financials_result = await run_supervisor_analysis(
            ticker, thread_id=f"{ticker}:sequential-baseline"
        )
        financials, ratios = financials_result["financials"], financials_result["ratios"]
    except SourceUnavailableError:
        financials, ratios = None, None
    sentiment = await run_news_sentiment(ticker)
    valuation = await run_valuation(ticker)
    await run_report_writer(
        ticker=ticker,
        financials=financials,
        ratios=ratios,
        sentiment=sentiment,
        valuation=valuation,
    )
    return time.monotonic() - start


async def main() -> None:
    settings = get_settings()
    pool = await open_pool(settings.postgres_url)
    checkpointer = AsyncPostgresSaver(conn=pool)  # type: ignore[arg-type]
    await checkpointer.setup()
    init_supervisor_graph(checkpointer)
    init_analyst_team_graph(checkpointer)

    try:
        tickers = [ticker for peers in TICKERS_BY_SECTOR.values() for ticker in peers]
        print(f"Running {len(tickers)} tickers across {len(TICKERS_BY_SECTOR)} sectors...\n")

        results: list[tuple[str, float, bool, str, bool]] = []
        for ticker in tickers:
            elapsed, ok, error = await _time_team_run(ticker)
            benchmark = await fetch_sector_benchmark(ticker)
            benchmark_ok = benchmark.median_pe is not None or benchmark.median_pb is not None
            results.append((ticker, elapsed, ok, error, benchmark_ok))
            status = "PASS" if ok else f"FAIL ({error})"
            print(
                f"{ticker:6s} {elapsed:6.1f}s  {status}  "
                f"benchmark={'ok' if benchmark_ok else 'degraded'}"
            )

        passed = sum(1 for _, _, ok, _, _ in results if ok)
        benchmark_successes = sum(1 for *_, benchmark_ok in results if benchmark_ok)
        avg_time = sum(elapsed for _, elapsed, *_ in results) / len(results)

        print(f"\n{passed}/{len(results)} tickers passed")
        print(f"benchmark-fetch success rate: {benchmark_successes}/{len(results)}")
        print(f"average time per ticker: {avg_time:.1f}s (budget: {TIME_BUDGET_SECONDS:.0f}s)")
        if avg_time > TIME_BUDGET_SECONDS:
            print(
                f"WARNING: average time {avg_time:.1f}s exceeds the "
                f"{TIME_BUDGET_SECONDS:.0f}s budget"
            )

        parallel_time, _, _ = await _time_team_run(SPEEDUP_TICKER)
        sequential_time = await _time_sequential_baseline(SPEEDUP_TICKER)
        speedup = sequential_time / parallel_time if parallel_time else float("nan")
        print(
            f"\nspeedup sample ({SPEEDUP_TICKER}): sequential={sequential_time:.1f}s "
            f"parallel={parallel_time:.1f}s speedup={speedup:.2f}x"
        )
    finally:
        await close_pool(pool)


if __name__ == "__main__":
    asyncio.run(main())
