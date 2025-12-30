from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration using environment variables."""

    # Application settings
    app_name: str = "Bookmark Validation Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8002

    # Kafka configuration
    kafka_bootstrap_servers: str = "bookmark-kafka:9092"
    kafka_topic: str = "bookmarks.bookmark.created"
    kafka_consumer_group: str = "validation-service"
    kafka_validation_topic: str = "bookmarks.validation.completed"
    kafka_auto_offset_reset: str = "earliest"
    kafka_session_timeout_ms: int = 30000
    kafka_max_poll_records: int = 10

    # Validation settings
    validation_timeout_seconds: int = 10
    validation_max_attempts: int = 3
    validation_initial_retry_delay: float = 1.0
    validation_max_retry_delay: float = 10.0
    validation_backoff_multiplier: float = 2.0
    validation_user_agent: str = "BookmarkValidator/1.0"

    # Scheduler settings (optional - can be disabled for external scheduling)
    enable_scheduler: bool = True  # Set to false to disable internal scheduler
    revalidation_interval_hours: int = 24
    revalidation_batch_size: int = 100
    revalidation_stale_threshold_days: int = 7

    # Bookmark Service API configuration (ALL data access goes through this)
    bookmark_service_host: str = "bookmark-service"
    bookmark_service_port: int = 8000
    bookmark_service_timeout_seconds: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @property
    def bookmark_service_url(self) -> str:
        """Construct bookmark service base URL."""
        return f"http://{self.bookmark_service_host}:{self.bookmark_service_port}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern)."""
    return Settings()
