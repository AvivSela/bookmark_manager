"""Dataset enricher - extracts dataset metadata without downloading files."""

import time
import httpx
import logging
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from app.enrichers.core.base_enricher import (
    BaseEnricher,
    EnricherContext,
    EnricherResult,
)
from app.enrichers.core.resource_types import ResourceType
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DatasetEnricher(BaseEnricher):
    """Extract dataset metadata from URL patterns and platform pages."""

    # Platform-specific patterns and scraping configs
    PLATFORM_PATTERNS = {
        "kaggle": {
            "pattern": r"kaggle\.com/datasets/([^/]+)/([^/?]+)",
            "scrape_selectors": {
                "title": ["h1", "h1.sc-eDvSVe"],
                "description": ["div.dataset-description", "div.sc-fzpjYC"],
            },
        },
        "data_gov": {
            "pattern": r"data\.gov/dataset/([^/?]+)",
            "scrape_selectors": {
                "title": ["h1"],
                "description": ["div.notes", "section.notes"],
            },
        },
        "github": {
            "pattern": r"github\.com/.+?\.(csv|json|parquet|xml|tsv)(\?|$)",
        },
    }

    # File format detection
    FORMAT_EXTENSIONS = {
        ".csv": "csv",
        ".json": "json",
        ".xml": "xml",
        ".tsv": "tsv",
        ".parquet": "parquet",
        ".xlsx": "excel",
        ".xls": "excel",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for platform detection."""
        self.compiled_patterns = {}
        for platform, config in self.PLATFORM_PATTERNS.items():
            if "pattern" in config:
                self.compiled_patterns[platform] = re.compile(
                    config["pattern"], re.IGNORECASE
                )

    async def enrich(self, context: EnricherContext) -> EnricherResult:
        """
        Enrich dataset by extracting metadata without downloading files.

        Strategy:
        1. Detect platform from URL
        2. Extract metadata using platform-specific strategy
        3. Fallback to generic extraction if platform unknown

        Args:
            context: Enrichment context with URL and metadata

        Returns:
            EnricherResult with dataset metadata
        """
        start_time = time.time()

        try:
            # Step 1: Detect platform
            platform = self._detect_platform(context.url)

            # Step 2: Extract metadata
            if platform and settings.dataset_enable_platform_scraping:
                metadata = await self._extract_platform_metadata(context.url, platform)
            else:
                metadata = await self._extract_generic_metadata(context.url)

            # Step 3: Detect format from URL if not found
            if not metadata.get("format"):
                metadata["format"] = self._detect_format_from_url(context.url)

            # Step 4: Add platform info
            metadata["platform"] = platform or "unknown"

            execution_time = (time.time() - start_time) * 1000

            return EnricherResult(
                enricher=self,
                success=True,
                data={"dataset_metadata": metadata},
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(f"Failed to enrich dataset {context.url}: {e}")

            return EnricherResult(
                enricher=self,
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )

    def _detect_platform(self, url: str) -> Optional[str]:
        """
        Detect platform from URL patterns.

        Args:
            url: Dataset URL

        Returns:
            Platform name or None
        """
        for platform, pattern in self.compiled_patterns.items():
            if pattern.search(url):
                return platform
        return None

    async def _extract_platform_metadata(
        self, url: str, platform: str
    ) -> Dict[str, Any]:
        """
        Extract metadata using platform-specific scraping.

        Args:
            url: Dataset URL
            platform: Detected platform name

        Returns:
            Dict with extracted metadata
        """
        timeout = httpx.Timeout(settings.dataset_timeout_seconds)
        headers = {"User-Agent": settings.user_agent}

        metadata = {}

        try:
            # Fetch page HTML
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                # Check response size
                if len(response.content) > settings.dataset_max_page_size:
                    self.logger.warning(
                        f"Page size exceeds limit, truncating to {settings.dataset_max_page_size} bytes"
                    )

                # Parse HTML
                soup = BeautifulSoup(
                    response.text[: settings.dataset_max_page_size], "lxml"
                )

            # Extract metadata using platform selectors
            config = self.PLATFORM_PATTERNS[platform]
            selectors = config.get("scrape_selectors", {})

            for field, selector_list in selectors.items():
                value = self._extract_from_selectors(soup, selector_list)
                if value:
                    metadata[field] = value

        except Exception as e:
            self.logger.warning(
                f"Platform scraping failed for {platform}: {e}. "
                f"Falling back to generic extraction."
            )
            # Fallback to generic extraction on error
            metadata = await self._extract_generic_metadata(url)

        return metadata

    def _extract_from_selectors(
        self, soup: BeautifulSoup, selectors: list
    ) -> Optional[str]:
        """
        Try multiple CSS selectors and return first match.

        Args:
            soup: BeautifulSoup parsed HTML
            selectors: List of CSS selectors to try

        Returns:
            Extracted text or None
        """
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text:
                    return text
        return None

    async def _extract_generic_metadata(self, url: str) -> Dict[str, Any]:
        """
        Generic metadata extraction for unknown platforms.

        Uses HEAD request to get Content-Length and Content-Type.

        Args:
            url: Dataset URL

        Returns:
            Dict with basic metadata
        """
        timeout = httpx.Timeout(settings.dataset_timeout_seconds)
        headers = {"User-Agent": settings.user_agent}

        metadata = {}

        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                response = await client.head(url, headers=headers)
                response.raise_for_status()

                # Extract size
                content_length = response.headers.get("content-length")
                if content_length:
                    metadata["size"] = self._format_file_size(int(content_length))

                # Extract format from Content-Type
                content_type = response.headers.get("content-type", "")
                format_from_ct = self._content_type_to_format(content_type)
                if format_from_ct:
                    metadata["format"] = format_from_ct

                # Try to extract filename from Content-Disposition
                content_disp = response.headers.get("content-disposition", "")
                if "filename=" in content_disp:
                    # Extract filename for additional context
                    filename_match = re.search(r'filename="?([^"]+)"?', content_disp)
                    if filename_match:
                        metadata["filename"] = filename_match.group(1)

        except Exception as e:
            self.logger.warning(f"Generic metadata extraction failed: {e}")

        return metadata

    def _detect_format_from_url(self, url: str) -> Optional[str]:
        """
        Extract format from file extension in URL.

        Args:
            url: Dataset URL

        Returns:
            Format string or None
        """
        parsed = urlparse(url)
        path = parsed.path.lower()

        for ext, format_name in self.FORMAT_EXTENSIONS.items():
            if path.endswith(ext):
                return format_name

        return None

    def _content_type_to_format(self, content_type: str) -> Optional[str]:
        """
        Map Content-Type header to dataset format.

        Args:
            content_type: HTTP Content-Type header value

        Returns:
            Format string or None
        """
        content_type_lower = content_type.lower()

        mappings = {
            "text/csv": "csv",
            "application/csv": "csv",
            "application/json": "json",
            "text/xml": "xml",
            "application/xml": "xml",
            "application/x-parquet": "parquet",
            "application/vnd.ms-excel": "excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
        }

        for ct, fmt in mappings.items():
            if ct in content_type_lower:
                return fmt

        return None

    def _format_file_size(self, bytes_size: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            bytes_size: Size in bytes

        Returns:
            Formatted size string
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"

    def is_applicable(self, resource_type: ResourceType) -> bool:
        """
        DatasetEnricher applies only to DATASET resource types.

        Args:
            resource_type: Detected resource type

        Returns:
            True if resource is DATASET
        """
        return resource_type == ResourceType.DATASET

    @property
    def name(self) -> str:
        """Enricher name."""
        return "dataset"

    @property
    def required(self) -> bool:
        """DatasetEnricher is optional (not required)."""
        return False

    @property
    def timeout(self) -> float:
        """Timeout for dataset enrichment."""
        return self.config.get("timeout", settings.dataset_timeout_seconds)
