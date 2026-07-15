# Testing

- Backend tests use `pytest`, live under `tests/`, mirror the `app/` module layout.
- Parser/adapter tests include missing keys, malformed values, duplicate identities, and
  out-of-order periods—not only happy-path vendor payloads.
- Regression fixtures must execute the guarded branch and fail against the precise broken
  behavior; tests that mutate module globals must restore them with `monkeypatch`.
- Cache/database changes test transaction boundaries, idempotent re-ingestion, stale fallback,
  and that network work runs without a checked-out database connection.
- Service behavior changes require one real API exercise and inspection of process/container
  logs in addition to unit tests.
- No mocking the Weaviate Cloud client in integration tests — use a disposable test collection.
- Frontend has no test suite yet; add one only when component logic becomes non-trivial.
