from __future__ import annotations

import pytest

from app.agents.tools import web_search


class _FakeTavilyClient:
    def __init__(
        self, results: list[dict[str, str]] | None = None, *, raises: Exception | None = None
    ) -> None:
        self._results = results if results is not None else []
        self._raises = raises
        self.last_call: dict[str, object] = {}

    async def search(self, query: str, **kwargs: object) -> dict[str, object]:
        self.last_call = {"query": query, **kwargs}
        if self._raises is not None:
            raise self._raises
        return {"results": self._results}


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_search, "_client", None)


@pytest.mark.asyncio
async def test_web_search_tool_maps_tavily_results(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeTavilyClient(
        results=[
            {
                "title": "AAPL surges",
                "url": "https://example.com/1",
                "content": "Apple stock rises.",
            },
            {"title": "AAPL dips", "url": "https://example.com/2", "content": "Apple stock falls."},
        ]
    )
    monkeypatch.setattr(web_search, "_client", fake_client)

    results = await web_search.web_search_tool("AAPL stock news", days=30, max_results=10)

    assert results == [
        {"title": "AAPL surges", "url": "https://example.com/1", "content": "Apple stock rises."},
        {"title": "AAPL dips", "url": "https://example.com/2", "content": "Apple stock falls."},
    ]
    assert fake_client.last_call["query"] == "AAPL stock news"
    assert fake_client.last_call["topic"] == "news"
    assert fake_client.last_call["days"] == 30
    assert fake_client.last_call["max_results"] == 10


@pytest.mark.asyncio
async def test_web_search_tool_returns_empty_list_on_no_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_search, "_client", _FakeTavilyClient(results=[]))

    results = await web_search.web_search_tool("obscure ticker news")

    assert results == []


@pytest.mark.asyncio
async def test_web_search_tool_tolerates_a_response_missing_the_results_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed/empty Tavily response (no "results" key at all) must degrade to an
    empty list rather than raising KeyError (caught in PR review)."""

    class _MalformedClient:
        async def search(self, query: str, **kwargs: object) -> dict[str, object]:
            return {}

    monkeypatch.setattr(web_search, "_client", _MalformedClient())

    results = await web_search.web_search_tool("AAPL stock news")

    assert results == []


@pytest.mark.asyncio
async def test_web_search_tool_tolerates_a_result_missing_expected_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An individual result missing "title"/"url"/"content" must degrade to empty strings
    for those fields rather than raising KeyError (caught in PR review)."""
    fake_client = _FakeTavilyClient(results=[{"title": "AAPL surges"}])
    monkeypatch.setattr(web_search, "_client", fake_client)

    results = await web_search.web_search_tool("AAPL stock news")

    assert results == [{"title": "AAPL surges", "url": "", "content": ""}]


@pytest.mark.asyncio
async def test_web_search_tool_tolerates_a_none_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the Tavily client returns None or a non-dict (unexpected client behavior), must
    degrade to an empty list rather than raising AttributeError on `.get()` (caught in PR
    review)."""

    class _NoneReturningClient:
        async def search(self, query: str, **kwargs: object) -> None:
            return None

    monkeypatch.setattr(web_search, "_client", _NoneReturningClient())

    results = await web_search.web_search_tool("AAPL stock news")

    assert results == []
