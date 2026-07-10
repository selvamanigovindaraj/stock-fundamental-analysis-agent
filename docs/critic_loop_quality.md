# Critic Loop Quality Measurement

Run:

```bash
uv run python scripts/evaluate_critic_loop.py
```

The script runs the analyst team for 10 tickers, records the first draft critic score and
final post-revision critic score, and fails if average improvement is below `0.10`.

Latest live run (2026-07-10):

These LLM-graded scores are illustrative, non-deterministic evidence. Re-run the
evaluation periodically after prompt or model changes rather than treating this as a
permanent baseline.

```text
AAPL   first=0.65 final=0.85 improvement=+0.20 flag=accepted
MSFT   first=0.55 final=0.85 improvement=+0.30 flag=accepted
JNJ    first=0.55 final=0.00 improvement=-0.55 flag=max_revisions_reached
UNH    first=0.55 final=0.95 improvement=+0.40 flag=accepted
XOM    first=0.60 final=0.85 improvement=+0.25 flag=accepted
CVX    first=0.45 final=0.75 improvement=+0.30 flag=max_revisions_reached
JPM    first=0.55 final=0.75 improvement=+0.20 flag=max_revisions_reached
BAC    first=0.55 final=0.55 improvement=+0.00 flag=max_revisions_reached
AMZN   first=0.35 final=0.88 improvement=+0.53 flag=accepted
TSLA   first=0.55 final=0.87 improvement=+0.32 flag=accepted

average improvement: +0.19
```

Caveat: every ticker in this run hit the existing news-sentiment structured-output
degrade-to-neutral path before report generation, so this verifies the critic loop under
degraded sentiment context.
