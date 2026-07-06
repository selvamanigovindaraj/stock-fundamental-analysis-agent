# Stock Fundamental Analyser

Multi-agent stock fundamental analysis agent.

## Stack

- Backend: FastAPI + LangGraph + LangChain, Python 3.11, `uv`
- Vector store: Weaviate Cloud (no local vector DB service)
- LLM: DeepSeek (`deepseek-chat`), accessed via the OpenAI-compatible API at `https://api.deepseek.com`
- Web search: Tavily
- Frontend: React 19 + Vite + TypeScript + Tailwind CSS

## Run

```
cp .env.example .env   # fill in API keys + Weaviate Cloud URL/key
docker compose up --build
```

Backend: http://localhost:8000
Frontend: http://localhost:5173

## Conventions

- Backend imports use the `app.*` prefix; run uvicorn from the project root (`uvicorn app.main:app`).
- Everything is currently a stub (`raise NotImplementedError` / `pass`) — see `.claude/rules/` for style and testing conventions.
