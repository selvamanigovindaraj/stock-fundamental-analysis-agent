# Testing

- Backend tests use `pytest`, live under `tests/`, mirror the `app/` module layout.
- No mocking the Weaviate Cloud client in integration tests — use a disposable test collection.
- Frontend has no test suite yet; add one only when component logic becomes non-trivial.
