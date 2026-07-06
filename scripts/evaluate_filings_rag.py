from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path

# ragas==0.4.3 unconditionally imports langchain_community.chat_models.vertexai.ChatVertexAI,
# which doesn't exist in any langchain-community release compatible with this project's
# already-resolved langchain>=1.0 (verified: pinning langchain-community to an old pre-1.0
# release to keep that shim creates an unsatisfiable resolver conflict with langgraph/
# langchain-openai already used elsewhere). We never use VertexAI -- a stub is sufficient.
_vertexai_stub = types.ModuleType("langchain_community.chat_models.vertexai")


class _StubChatVertexAI:
    pass


_vertexai_stub.ChatVertexAI = _StubChatVertexAI  # type: ignore[attr-defined]
sys.modules.setdefault("langchain_community.chat_models.vertexai", _vertexai_stub)

from openai import AsyncOpenAI  # noqa: E402
from ragas.llms import llm_factory  # noqa: E402
from ragas.metrics.collections import ContextRecall, Faithfulness  # noqa: E402

from app.agents.filings_rag_graph import answer_filing_question  # noqa: E402
from app.config import get_settings  # noqa: E402

FAITHFULNESS_THRESHOLD = 0.85
CONTEXT_RECALL_THRESHOLD = 0.80
FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "filings_qa.json"


@dataclass
class EvalRow:
    user_input: str
    response: str
    retrieved_contexts: list[str]
    reference: str


async def _build_rows(pairs: list[dict[str, str]]) -> list[EvalRow]:
    rows = []
    for pair in pairs:
        result = await answer_filing_question(pair["question"], pair["ticker"])
        rows.append(
            EvalRow(
                user_input=pair["question"],
                response=result.answer,
                retrieved_contexts=[doc.content for doc in result.citations] or [""],
                reference=pair["reference_answer"],
            )
        )
    return rows


async def main() -> None:
    settings = get_settings()
    pairs = json.loads(FIXTURE_PATH.read_text())
    rows = await _build_rows(pairs)

    async with AsyncOpenAI(
        api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url
    ) as client:
        # ragas's instructor-based llm_factory defaults max_tokens=1024, too small for
        # statement generation over a full filing excerpt -- raise it to avoid
        # IncompleteOutputException.
        llm = llm_factory(settings.deepseek_model_generation, client=client, max_tokens=4096)
        faithfulness_metric = Faithfulness(llm=llm)
        context_recall_metric = ContextRecall(llm=llm)

        faithfulness_scores = [
            (
                await faithfulness_metric.ascore(
                    user_input=row.user_input,
                    response=row.response,
                    retrieved_contexts=row.retrieved_contexts,
                )
            ).value
            for row in rows
        ]
        context_recall_scores = [
            (
                await context_recall_metric.ascore(
                    user_input=row.user_input,
                    retrieved_contexts=row.retrieved_contexts,
                    reference=row.reference,
                )
            ).value
            for row in rows
        ]

    faithfulness = sum(faithfulness_scores) / len(faithfulness_scores)
    context_recall = sum(context_recall_scores) / len(context_recall_scores)

    print(f"faithfulness:   {faithfulness:.3f}  (threshold {FAITHFULNESS_THRESHOLD})")
    print(f"context_recall: {context_recall:.3f}  (threshold {CONTEXT_RECALL_THRESHOLD})")
    print(
        f"\nNOTE: this is a {len(pairs)}-pair seed set, not the 30-pair requirement -- scores "
        "here are directional only, not a statistically meaningful acceptance gate. Scaling "
        "to 30 real, verified pairs is a content-curation task, not a coding gap."
    )

    if faithfulness < FAITHFULNESS_THRESHOLD or context_recall < CONTEXT_RECALL_THRESHOLD:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
