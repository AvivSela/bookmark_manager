"""Base enricher interface and data structures."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging
import asyncio
import time

from app.enrichers.core.resource_types import ResourceType


@dataclass
class EnricherContext:
    """Context passed to all enrichers."""

    url: str
    bookmark_id: str
    tenant_id: str
    resource_type: ResourceType
    timeout: float
    # Optional cached data from previous enrichers
    html_content: Optional[str] = None
    http_response: Optional[Any] = None  # httpx.Response


@dataclass
class EnricherResult:
    """Result from a single enricher."""

    enricher: "BaseEnricher"
    success: bool
    data: Dict[str, Any]  # Enriched fields
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class BaseEnricher(ABC):
    """Abstract base class for all enrichers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)

    async def enrich_safe(self, context: EnricherContext) -> EnricherResult:
        """
        Safe wrapper around enrich() that handles timeouts and exceptions.

        This is the method that should be called by orchestrators.
        It ensures that EnricherResult is always returned, never an exception.

        Args:
            context: Enrichment context with URL, type, etc.

        Returns:
            EnricherResult - always returns a result, never raises
        """
        start_time = time.time()

        try:
            # Run enrichment with timeout
            result = await asyncio.wait_for(self.enrich(context), timeout=self.timeout)
            return result

        except asyncio.TimeoutError:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(f"Enricher {self.name} timed out after {self.timeout}s")
            return EnricherResult(
                enricher=self,
                success=False,
                data={},
                error=f"Timeout after {self.timeout}s",
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(f"Enricher {self.name} raised exception: {e}", exc_info=e)
            return EnricherResult(
                enricher=self,
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )

    @abstractmethod
    async def enrich(self, context: EnricherContext) -> EnricherResult:
        """
        Perform enrichment on the given resource.

        Must be implemented by subclasses.

        Args:
            context: Enrichment context with URL, type, etc.

        Returns:
            EnricherResult with extracted data or error
        """
        pass

    @abstractmethod
    def is_applicable(self, resource_type: ResourceType) -> bool:
        """
        Determine if this enricher applies to the resource type.

        Args:
            resource_type: Detected resource type

        Returns:
            True if enricher should run for this type
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this enricher."""
        pass

    @property
    def timeout(self) -> float:
        """Timeout in seconds for this enricher (override if needed)."""
        return self.config.get("timeout", 10.0)

    @property
    def required(self) -> bool:
        """
        Whether this enricher is required for successful enrichment.

        If False, failures are logged but don't fail the entire enrichment.
        """
        return self.config.get("required", False)
