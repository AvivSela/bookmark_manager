from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration using environment variables."""

    # Application settings
    app_name: str = "Bookmark Enrichment Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8001

    # Database configuration
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Kafka configuration
    kafka_bootstrap_servers: str = "bookmark-kafka:9092"
    kafka_topic: str = "bookmarks.bookmark.created"
    kafka_consumer_group: str = "enrichment-service"
    kafka_auto_offset_reset: str = "earliest"
    kafka_session_timeout_ms: int = 30000
    kafka_max_poll_records: int = 10

    # Enrichment settings
    enrichment_timeout_seconds: int = 10
    enrichment_max_attempts: int = 5
    enrichment_initial_retry_delay: float = 1.0
    enrichment_max_retry_delay: float = 60.0
    enrichment_backoff_multiplier: float = 2.0
    user_agent: str = "BookmarkEnricher/1.0 (+https://example.com/bot)"

    # Bookmark Service configuration
    bookmark_service_host: str = "bookmark-service"
    bookmark_service_port: int = 8000
    bookmark_service_timeout_seconds: int = 10

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def bookmark_service_url(self) -> str:
        """Construct bookmark service base URL."""
        return f"http://{self.bookmark_service_host}:{self.bookmark_service_port}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern)."""
    return Settings()
