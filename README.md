# Stock Fundamental Analyser

Multi-agent stock fundamental analysis agent.

## Stack

- Backend: FastAPI + LangGraph + LangChain, Python 3.12, `uv`
- Vector store: Weaviate Cloud (no local vector DB service)
- LLM: DeepSeek (`deepseek-chat`), accessed via the OpenAI-compatible API at `https://api.deepseek.com`
- Embeddings/rerank: Voyage AI
- Checkpointing: Postgres (`langgraph-checkpoint-postgres`)
- Web search: Tavily
- Frontend: React 19 + Vite + TypeScript + Tailwind CSS

## Run

```
cp .env.example .env   # fill in API keys + Weaviate Cloud URL/key
docker compose up --build
```

Backend: http://localhost:8001
Frontend: http://localhost:5174

(Host ports are remapped from the containers' defaults of 8000/5173 in `docker-compose.yml` to avoid clashing with other projects' containers on this machine — adjust back if you don't have that conflict.)

## Development

```
uv sync
make check   # lint + type-check + tests
```

See `CLAUDE.md` and `.claude/rules/` for conventions.

## License

MIT — see [LICENSE](LICENSE).
