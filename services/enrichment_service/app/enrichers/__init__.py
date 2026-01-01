"""Enrichment service - organized enricher modules."""

# Import from submodules for backward compatibility
from app.enrichers.core import (
    BaseEnricher,
    EnricherContext,
    EnricherResult,
    EnricherRegistry,
    registry,
    EnrichmentOrchestrator,
    ResourceTypeDetector,
    ResourceDetectorConfig,
    ResourceType,
    ResourceTypeInfo,
    EnrichmentRetryHandler,
)

from app.enrichers.clients import (
    BookmarkServiceClient,
)

from app.enrichers.implementations import (
    ApiEnricher,
    DatasetEnricher,
    ImageEnricher,
    WebPageEnricher,
)

__all__ = [
    # Core
    "BaseEnricher",
    "EnricherContext",
    "EnricherResult",
    "EnricherRegistry",
    "registry",
    "EnrichmentOrchestrator",
    "ResourceTypeDetector",
    "ResourceDetectorConfig",
    "ResourceType",
    "ResourceTypeInfo",
    "EnrichmentRetryHandler",
    # Clients
    "BookmarkServiceClient",
    # Implementations
    "ApiEnricher",
    "DatasetEnricher",
    "ImageEnricher",
    "WebPageEnricher",
]
