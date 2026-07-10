from __future__ import annotations

from tavily import AsyncTavilyClient

from app.config import get_settings

_client: AsyncTavilyClient | None = None


def _get_client() -> AsyncTavilyClient:
    global _client
    if _client is None:
        _client = AsyncTavilyClient(api_key=get_settings().tavily_api_key)
    return _client


async def web_search_tool(
    query: str, *, days: int = 30, max_results: int = 10
) -> list[dict[str, str]]:
    """Tavily-backed news search tool for agent use."""
    response = await _get_client().search(query, topic="news", days=days, max_results=max_results)
    if not response or not isinstance(response, dict):
        return []
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in response.get("results", [])
    ]
