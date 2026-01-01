from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional, List


class Settings(BaseSettings):
    """Application configuration using environment variables."""

    # Application settings
    app_name: str = "Bookmark Enrichment Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8001

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

    # ===== Enrichment Configuration =====

    # Enabled enrichers (comma-separated list)
    enabled_enrichers: str = "webpage,image,dataset,api"
    max_parallel_enrichers: int = 5


    # Image enricher settings
    image_max_header_size: int = 32 * 1024  # 32KB
    image_timeout_seconds: float = 10.0

    # Dataset enricher settings
    dataset_enable_platform_scraping: bool = True
    dataset_timeout_seconds: float = 15.0
    dataset_max_page_size: int = 5 * 1024 * 1024  # 5MB

    # API enricher settings
    api_spec_paths: str = "/openapi.json,/swagger.json,/api-docs"
    api_enable_html_fallback: bool = True
    api_timeout_seconds: float = 10.0

    # Screenshot service configuration (for Phase 2)
    screenshot_api_provider: str = "screenshotapi"
    screenshot_api_key: Optional[str] = None
    screenshot_api_endpoint: str = "https://api.screenshotapi.net/screenshot"
    screenshot_enabled: bool = False  # Disabled until Phase 2
    screenshot_timeout: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    @property
    def bookmark_service_url(self) -> str:
        """Construct bookmark service base URL."""
        return f"http://{self.bookmark_service_host}:{self.bookmark_service_port}"

    @property
    def enabled_enrichers_list(self) -> List[str]:
        """Parse enabled_enrichers string into list."""
        return [e.strip() for e in self.enabled_enrichers.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern)."""
    return Settings()
