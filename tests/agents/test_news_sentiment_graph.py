from __future__ import annotations

import pytest

from app.agents import news_sentiment_graph
from app.models import ArticleSentiment, NewsSentimentResult


class _FakeSentimentLLM:
    def __init__(
        self, result: NewsSentimentResult | None = None, *, raises: Exception | None = None
    ) -> None:
        self._result = result
        self._raises = raises
        self.invoke_count = 0
        self.last_prompt = ""

    async def ainvoke(self, prompt: str) -> NewsSentimentResult:
        self.invoke_count += 1
        self.last_prompt = prompt
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


def _articles() -> list[dict[str, str]]:
    return [
        {
            "title": "AAPL surges on strong earnings",
            "url": "https://example.com/1",
            "content": "Apple beat estimates.",
        },
        {
            "title": "AAPL faces supply concerns",
            "url": "https://example.com/2",
            "content": "Supply chain worries persist.",
        },
    ]


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(news_sentiment_graph, "_sentiment_llm", None)


@pytest.mark.asyncio
async def test_run_news_sentiment_scores_articles_in_one_batched_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    articles = _articles()

    async def fake_web_search_tool(query: str, **kwargs: object) -> list[dict[str, str]]:
        return articles

    monkeypatch.setattr(news_sentiment_graph, "web_search_tool", fake_web_search_tool)

    expected = NewsSentimentResult(
        ticker="AAPL",
        sentiment="positive",
        score=0.65,
        key_themes=["earnings beat", "supply chain"],
        articles=[
            ArticleSentiment(
                title=articles[0]["title"], url=articles[0]["url"], sentiment="positive", score=0.8
            ),
            ArticleSentiment(
                title=articles[1]["title"], url=articles[1]["url"], sentiment="negative", score=0.3
            ),
        ],
    )
    fake_llm = _FakeSentimentLLM(result=expected)
    monkeypatch.setattr(news_sentiment_graph, "_sentiment_llm", fake_llm)

    result = await news_sentiment_graph.run_news_sentiment("AAPL")

    assert result == expected
    assert fake_llm.invoke_count == 1  # one batched call, not one per article
    assert "AAPL surges on strong earnings" in fake_llm.last_prompt
    assert "AAPL faces supply concerns" in fake_llm.last_prompt


@pytest.mark.asyncio
async def test_run_news_sentiment_degrades_to_neutral_on_zero_articles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_web_search_tool(query: str, **kwargs: object) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(news_sentiment_graph, "web_search_tool", fake_web_search_tool)
    fake_llm = _FakeSentimentLLM()
    monkeypatch.setattr(news_sentiment_graph, "_sentiment_llm", fake_llm)

    result = await news_sentiment_graph.run_news_sentiment("ZZZZ")

    assert result.sentiment == "neutral"
    assert result.score == 0.5
    assert result.key_themes == []
    assert result.articles == []
    assert fake_llm.invoke_count == 0  # never call the LLM with no articles


@pytest.mark.asyncio
async def test_run_news_sentiment_degrades_to_neutral_on_llm_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_web_search_tool(query: str, **kwargs: object) -> list[dict[str, str]]:
        return _articles()

    monkeypatch.setattr(news_sentiment_graph, "web_search_tool", fake_web_search_tool)
    monkeypatch.setattr(
        news_sentiment_graph,
        "_sentiment_llm",
        _FakeSentimentLLM(raises=RuntimeError("DeepSeek down")),
    )

    result = await news_sentiment_graph.run_news_sentiment("AAPL")

    assert result.sentiment == "neutral"
    assert result.score == 0.5


@pytest.mark.asyncio
async def test_run_news_sentiment_degrades_to_neutral_when_llm_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """with_structured_output can return None (rather than raising) if the model's output
    fails to parse -- run_news_sentiment must still honor its "never raises" contract
    instead of hitting the AssertionError in run_news_sentiment's own None-check (caught
    in PR review)."""

    async def fake_web_search_tool(query: str, **kwargs: object) -> list[dict[str, str]]:
        return _articles()

    class _NoneReturningLLM:
        async def ainvoke(self, prompt: str) -> None:
            return None

    monkeypatch.setattr(news_sentiment_graph, "web_search_tool", fake_web_search_tool)
    monkeypatch.setattr(news_sentiment_graph, "_sentiment_llm", _NoneReturningLLM())

    result = await news_sentiment_graph.run_news_sentiment("AAPL")

    assert result.sentiment == "neutral"
    assert result.score == 0.5


@pytest.mark.asyncio
async def test_run_news_sentiment_degrades_to_neutral_on_search_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_web_search_tool_raises(query: str, **kwargs: object) -> list[dict[str, str]]:
        raise RuntimeError("Tavily down")

    monkeypatch.setattr(news_sentiment_graph, "web_search_tool", fake_web_search_tool_raises)

    result = await news_sentiment_graph.run_news_sentiment("AAPL")

    assert result.sentiment == "neutral"
    assert result.articles == []
