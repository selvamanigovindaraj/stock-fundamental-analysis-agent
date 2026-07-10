from __future__ import annotations

import os

# Must be set before the first `langgraph` import anywhere in this process --
# STRICT_MSGPACK_ENABLED is read once from this env var at import time, and it gates
# whether StateGraph.compile() derives a checkpoint msgpack allowlist from the graph's
# state schema (see app/agents/supervisor_graph.py and CLAUDE.md). Set as a real OS env
# var here (not just a pydantic-settings field) since this app is the process entrypoint.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.lifespan import lifespan  # noqa: E402
from app.routers import core, streaming  # noqa: E402

_settings = get_settings()
if _settings.langsmith_api_key:
    # Enables LangChain's global callback manager to auto-trace every LLM/graph run (e.g.
    # the analyst team's parallel branches) with no per-call code changes. Degrades to no
    # tracing, not a crash, if unconfigured -- matches this project's established
    # graceful-degradation posture elsewhere (LangSmith fallback logging, GAAP flag, etc).
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = _settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = _settings.langsmith_project

app = FastAPI(title="Multi Agent Stock Fundamental Analyser", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(core.router)
app.include_router(streaming.router)
