from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration using environment variables."""

    # Application settings
    app_name: str = "Bookmark API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database configuration
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"  # Docker service name
    postgres_port: int = 5432

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # Pagination defaults
    default_page_size: int = 50
    max_page_size: int = 100

    # Database connection pool settings
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Kafka configuration
    kafka_bootstrap_servers: str = "bookmark-kafka:9092"
    kafka_topic_prefix: str = "bookmarks"
    kafka_enabled: bool = True
    kafka_compression_type: str = "gzip"
    kafka_max_retries: int = 3
    kafka_request_timeout_ms: int = 30000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern)."""
    return Settings()
