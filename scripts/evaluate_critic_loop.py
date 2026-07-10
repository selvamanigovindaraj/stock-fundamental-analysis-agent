from __future__ import annotations

import asyncio
import os
from uuid import uuid4

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: E402

from app.agents.analyst_team_graph import init_analyst_team_graph, run_team_analysis  # noqa: E402
from app.agents.supervisor_graph import init_supervisor_graph  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import close_pool, open_pool  # noqa: E402

TICKERS = ["AAPL", "MSFT", "JNJ", "UNH", "XOM", "CVX", "JPM", "BAC", "AMZN", "TSLA"]
MIN_AVERAGE_IMPROVEMENT = 0.10


async def main() -> None:
    settings = get_settings()
    pool = await open_pool(settings.postgres_url)
    try:
        checkpointer = AsyncPostgresSaver(conn=pool)  # type: ignore[arg-type]
        await checkpointer.setup()
        init_supervisor_graph(checkpointer)
        init_analyst_team_graph(checkpointer)

        improvements: list[float] = []
        for ticker in TICKERS:
            try:
                result = await run_team_analysis(
                    ticker, thread_id=f"{ticker}:critic-eval:{uuid4().hex}"
                )
                first = result["first_critic_review"]
                final = result["critic_review"]
                if first is None or final is None:
                    raise RuntimeError("missing critic scores")
            except Exception as exc:  # noqa: BLE001 - keep evaluating the remaining tickers
                print(f"{ticker:6s} FAILED: {exc}")
                continue
            improvement = final.score - first.score
            improvements.append(improvement)
            print(
                f"{ticker:6s} first={first.score:.2f} final={final.score:.2f} "
                f"improvement={improvement:+.2f} flag={result['quality_flag']}"
            )

        if not improvements:
            raise SystemExit("no critic-loop evaluations succeeded")
        average = sum(improvements) / len(improvements)
        print(f"\naverage improvement: {average:+.2f}")
        if average < MIN_AVERAGE_IMPROVEMENT:
            raise SystemExit(
                f"average improvement {average:+.2f} is below "
                f"{MIN_AVERAGE_IMPROVEMENT:+.2f}"
            )
    finally:
        await close_pool(pool)


if __name__ == "__main__":
    asyncio.run(main())
