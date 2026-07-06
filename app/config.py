from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # DeepSeek (OpenAI-compatible API)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_generation: str = "deepseek-chat"
    deepseek_model_routing: str = "deepseek-chat"

    # Weaviate Cloud
    weaviate_url: str = ""
    weaviate_api_key: str = ""
    weaviate_class_name: str = "StockFundamentalIndex"

    # Tavily
    tavily_api_key: str = ""

    # App
    environment: str = "development"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
