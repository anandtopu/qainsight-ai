"""
QA Insight AI — Application Configuration
All settings loaded from environment variables with sensible defaults.
"""
from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — loaded from environment variables."""

    # ── Application ─────────────────────────────────────────
    APP_NAME: str = "QA Insight AI"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    APP_DEBUG: bool = False
    APP_VERSION: str = "3.0.0"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Database (PostgreSQL) ────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "qainsight"
    POSTGRES_USER: str = "qainsight_user"
    POSTGRES_PASSWORD: str = "changeme_local_dev"
    DATABASE_URL: str = "postgresql+asyncpg://qainsight_user:changeme_local_dev@localhost:5432/qainsight"

    # ── MongoDB ──────────────────────────────────────────────
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_DB: str = "qainsight_logs"
    MONGO_URI: str = "mongodb://localhost:27017"

    # ── MinIO (S3-compatible) ────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: str = "password123"
    MINIO_BUCKET_NAME: str = "test-telemetry"
    MINIO_USE_SSL: bool = False

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_WORKER_CONCURRENCY: int = 4

    # ── LLM Provider ─────────────────────────────────────────
    LLM_PROVIDER: Literal["ollama", "lmstudio", "localai", "vllm", "openai", "gemini"] = "ollama"
    LLM_MODEL: str = "qwen2.5:7b"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LMSTUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LOCALAI_BASE_URL: str = "http://localhost:8080/v1"
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # ── Embedding ─────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # ── ChromaDB ──────────────────────────────────────────────
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION: str = "qainsight_embeddings"

    # ── AI Agent ─────────────────────────────────────────────
    AI_OFFLINE_MODE: bool = True
    AI_CONFIDENCE_THRESHOLD: int = 80
    AI_MAX_RETRIES: int = 3
    AI_TIMEOUT_SECONDS: int = 120

    # ── Jira ─────────────────────────────────────────────────
    JIRA_ENABLED: bool = False
    JIRA_DOMAIN: Optional[str] = None
    JIRA_EMAIL: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None
    JIRA_DEFAULT_PROJECT_KEY: str = "QA"

    # ── Splunk ────────────────────────────────────────────────
    SPLUNK_ENABLED: bool = False
    SPLUNK_BASE_URL: Optional[str] = None
    SPLUNK_API_TOKEN: Optional[str] = None
    SPLUNK_INDEX: str = "main"

    # ── OpenShift / Kubernetes ────────────────────────────────
    OCP_ENABLED: bool = False
    OCP_API_URL: Optional[str] = None
    OCP_SA_TOKEN: Optional[str] = None
    OCP_DEFAULT_NAMESPACE: str = "qa-testing"

    # ── Slack ─────────────────────────────────────────────────
    SLACK_ENABLED: bool = False
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_DEFAULT_CHANNEL: str = "#qa-alerts"

    # ── Authentication & JWT ──────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Logging ───────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def chroma_host_url(self) -> str:
        return f"http://{self.CHROMA_HOST}:{self.CHROMA_PORT}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
