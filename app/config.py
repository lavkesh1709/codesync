from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Groq
    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"

    # Cohere
    cohere_api_key: str

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # Embedding
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    enable_reranking: bool = False

    # Ingestion
    max_file_size_mb: int = 1
    chunk_size_lines: int = 40
    chunk_overlap_lines: int = 5

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        allowed = {"development", "production"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}, got '{v}'")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{v}'")
        return v

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()