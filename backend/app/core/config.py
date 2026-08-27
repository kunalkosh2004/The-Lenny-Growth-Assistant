from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://lenny:lenny_dev_password@localhost:5432/lenny_growth_assistant"
    transcripts_dir: str = "./knowledge-source/lennys-podcast-transcripts/episodes"
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    # Long-form generation (e.g. the Ship 30 skill's ~1,250-word article
    # pass) can comfortably exceed 60s on a small local CPU model, so this
    # needs real headroom rather than a chat-response-sized budget.
    ollama_timeout_seconds: float = 180.0
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    google_api_key: str | None = None
    google_model: str = "gemini-2.0-flash"

    # Knowledge base / embeddings.
    # "ollama" keeps the demo fully local (model: nomic-embed-text).
    # "openai" requires OPENAI_API_KEY (model: text-embedding-3-small).
    embedding_provider: str = "ollama"
    ollama_embedding_model: str = "nomic-embed-text"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_timeout_seconds: float = 60.0
    ingestion_batch_size: int = 32

    # Chunking: target characters per chunk and overlap between neighbors.
    chunk_target_chars: int = 1200
    chunk_overlap_chars: int = 150

    # Minimum cosine-similarity score (0-1) for a retrieved chunk to be
    # considered relevant. Chunks below this are dropped before grounding,
    # so an off-topic question yields no context deterministically instead
    # of relying on the LLM to notice the context is unrelated.
    retrieval_min_score: float = 0.5
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
