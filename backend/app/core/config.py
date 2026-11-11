"""Configuración central cargada desde variables de entorno."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define opciones tipadas de aplicación, seguridad, datos e IA."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "La Biblioteca de Alejandria API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://alejandria:alejandria_dev@localhost:5433/alejandria"
    jwt_secret: str = Field(
        default="development-secret-change-before-production",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    cors_origins: str = "http://localhost:5173"

    ai_provider: str = "gemini"
    ai_api_key: str | None = None
    gemini_api_key: str | None = None
    ai_chat_model: str | None = "gemini-3.8-flash"
    ai_embedding_model: str | None = "gemini-embedding-001"
    ai_embedding_dimensions: int = Field(default=1536, ge=256, le=4096)
    ai_retry_attempts: int = Field(default=3, ge=1, le=5)
    ai_retry_backoff_seconds: float = Field(default=1.0, ge=0, le=10)
    ai_thinking_budget: int = Field(default=0, ge=-1, le=8192)
    external_api_timeout_seconds: float = Field(default=8.0, ge=1, le=30)
    external_api_user_agent: str = "BibliotecaAlejandria/0.1 (academic project)"
    wikimedia_user_agent: str | None = None
    rag_chunk_size: int = Field(default=1800, ge=500, le=8000)
    rag_chunk_overlap: int = Field(default=200, ge=0, le=2000)
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_index_batch_size: int = Field(default=20, ge=1, le=100)

    @property
    def cors_origin_list(self) -> list[str]:
        """Convierte la lista CORS separada por comas al formato de FastAPI."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de configuración por proceso."""
    return Settings()
