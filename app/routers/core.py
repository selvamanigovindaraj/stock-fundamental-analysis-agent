from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    raise NotImplementedError


@router.post("/chat")
async def chat() -> dict[str, str]:
    """Entry point for the multi-agent stock fundamental analysis pipeline."""
    raise NotImplementedError
