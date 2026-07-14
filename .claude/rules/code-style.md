# Code Style

- Python 3.12, type hints everywhere, `from __future__ import annotations` at the top of every module.
- Use `uv` for dependency management, not `pip` directly.
- FastAPI routes stay thin; business logic lives in `app/services`.
- LangGraph agents live in `app/agents`; tools live in `app/agents/tools`.
- Treat vendor dictionaries, dataframes, and API payloads as untrusted input: tolerate missing,
  malformed, duplicated, and out-of-order records at the adapter boundary.
- Never hold a database connection, lock, or transaction across network/vendor I/O; fetch and
  parse first, then open the shortest transaction that can commit the database work atomically.
- No new abstractions without a second concrete use case (YAGNI).
- TypeScript: strict mode, functional components, no class components.
