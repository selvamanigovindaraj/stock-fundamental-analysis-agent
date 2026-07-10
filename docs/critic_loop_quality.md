# Critic Loop Quality Measurement

Run:

```bash
uv run python scripts/evaluate_critic_loop.py
```

The script runs the analyst team for 10 tickers, records the first draft critic score and
final post-revision critic score, and fails if average improvement is below `0.10`.

Latest live run (2026-07-10):

```text
AAPL   first=0.55 final=0.85 improvement=+0.30 flag=accepted
MSFT   first=0.45 final=0.87 improvement=+0.42 flag=accepted
JNJ    first=0.65 final=0.88 improvement=+0.23 flag=accepted
UNH    first=0.45 final=0.75 improvement=+0.30 flag=max_revisions_reached
XOM    first=0.70 final=0.65 improvement=-0.05 flag=max_revisions_reached
CVX    first=0.45 final=0.65 improvement=+0.20 flag=max_revisions_reached
JPM    first=0.55 final=0.85 improvement=+0.30 flag=accepted
BAC    first=0.50 final=0.85 improvement=+0.35 flag=accepted
AMZN   first=0.35 final=0.85 improvement=+0.50 flag=accepted
TSLA   first=0.75 final=0.85 improvement=+0.10 flag=accepted

average improvement: +0.27
```

Caveat: every ticker in this run hit the existing news-sentiment structured-output
degrade-to-neutral path before report generation, so this verifies the critic loop under
degraded sentiment context.
