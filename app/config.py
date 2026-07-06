from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env")

    # DeepSeek (OpenAI-compatible API)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_generation: str = "deepseek-chat"
    deepseek_model_routing: str = "deepseek-chat"

    # Weaviate Cloud
    weaviate_url: str = ""
    weaviate_api_key: str = ""
    weaviate_filings_collection: str = "FilingSection"

    # Voyage AI (embeddings + reranking)
    voyage_api_key: str = ""
    voyage_embedding_model: str = "voyage-3"
    voyage_rerank_model: str = "rerank-2.5"

    # Tavily
    tavily_api_key: str = ""

    # SEC EDGAR
    sec_edgar_user_agent: str = ""

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_project: str = "stock-fundamental-analyser"

    # App
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
