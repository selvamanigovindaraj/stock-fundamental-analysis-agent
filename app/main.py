from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Multi Agent Stock Fundamental Analyser")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    raise NotImplementedError


@app.post("/chat")
async def chat() -> dict[str, str]:
    """Entry point for the multi-agent stock fundamental analysis pipeline."""
    raise NotImplementedError
