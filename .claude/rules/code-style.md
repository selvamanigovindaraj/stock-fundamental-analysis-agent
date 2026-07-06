# Code Style

- Python 3.11, type hints everywhere, `from __future__ import annotations` at the top of every module.
- Use `uv` for dependency management, not `pip` directly.
- FastAPI routes stay thin; business logic lives in `app/services`.
- LangGraph agents live in `app/agents`; tools live in `app/agents/tools`.
- No new abstractions without a second concrete use case (YAGNI).
- TypeScript: strict mode, functional components, no class components.
