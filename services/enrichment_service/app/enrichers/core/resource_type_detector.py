"""Resource type detection using multiple strategies."""

import re
import httpx
import logging
from typing import Optional, Dict, Pattern
from dataclasses import dataclass
from urllib.parse import urlparse
from pathlib import Path

from app.enrichers.core.resource_types import ResourceType, ResourceTypeInfo


logger = logging.getLogger(__name__)


@dataclass
class ResourceDetectorConfig:
    """Configuration for resource type detector."""

    enable_head_requests: bool = False
    head_request_timeout: float = 5.0


class ResourceTypeDetector:
    """Detect resource type using multiple strategies."""

    # URL pattern mapping to resource types
    URL_PATTERNS: Dict[ResourceType, list[str]] = {
        ResourceType.API: [
            r"api\.",  # api.example.com
            r"/api/",  # example.com/api/endpoint
            r"/v\d+/",  # example.com/v1/resource
            r"\.json$",  # example.com/data.json
        ],
        ResourceType.DATASET: [
            r"\.csv$",
            r"\.json$",
            r"\.xml$",
            r"\.tsv$",
            r"\.parquet$",
            r"/datasets?/",
            r"/data/",
        ],
        ResourceType.IMAGE: [
            r"\.(jpg|jpeg|png|gif|webp|svg|bmp|ico)$",
        ],
        ResourceType.VIDEO: [
            r"\.(mp4|webm|avi|mov|mkv|flv|wmv)$",
            r"youtube\.com/watch",
            r"youtu\.be/",
            r"vimeo\.com/\d+",
        ],
        ResourceType.AUDIO: [
            r"\.(mp3|wav|ogg|flac|aac|m4a)$",
        ],
        ResourceType.PDF: [
            r"\.pdf$",
        ],
        ResourceType.DOCUMENT: [
            r"\.(doc|docx|xls|xlsx|ppt|pptx|odt|ods|odp)$",
        ],
        ResourceType.ARCHIVE: [
            r"\.(zip|tar|gz|bz2|7z|rar)$",
        ],
        ResourceType.CODE: [
            r"github\.com/[^/]+/[^/]+$",  # GitHub repos
            r"gitlab\.com/[^/]+/[^/]+$",  # GitLab repos
            r"bitbucket\.org/[^/]+/[^/]+$",  # Bitbucket repos
        ],
    }

    # File extension mapping to resource types
    EXTENSION_MAP: Dict[str, ResourceType] = {
        # Data formats
        ".csv": ResourceType.DATASET,
        ".json": ResourceType.DATASET,
        ".xml": ResourceType.DATASET,
        ".tsv": ResourceType.DATASET,
        ".parquet": ResourceType.DATASET,
        # Images
        ".jpg": ResourceType.IMAGE,
        ".jpeg": ResourceType.IMAGE,
        ".png": ResourceType.IMAGE,
        ".gif": ResourceType.IMAGE,
        ".webp": ResourceType.IMAGE,
        ".svg": ResourceType.IMAGE,
        ".bmp": ResourceType.IMAGE,
        ".ico": ResourceType.IMAGE,
        # Videos
        ".mp4": ResourceType.VIDEO,
        ".webm": ResourceType.VIDEO,
        ".avi": ResourceType.VIDEO,
        ".mov": ResourceType.VIDEO,
        ".mkv": ResourceType.VIDEO,
        ".flv": ResourceType.VIDEO,
        ".wmv": ResourceType.VIDEO,
        # Audio
        ".mp3": ResourceType.AUDIO,
        ".wav": ResourceType.AUDIO,
        ".ogg": ResourceType.AUDIO,
        ".flac": ResourceType.AUDIO,
        ".aac": ResourceType.AUDIO,
        ".m4a": ResourceType.AUDIO,
        # Documents
        ".pdf": ResourceType.PDF,
        ".doc": ResourceType.DOCUMENT,
        ".docx": ResourceType.DOCUMENT,
        ".xls": ResourceType.DOCUMENT,
        ".xlsx": ResourceType.DOCUMENT,
        ".ppt": ResourceType.DOCUMENT,
        ".pptx": ResourceType.DOCUMENT,
        ".odt": ResourceType.DOCUMENT,
        ".ods": ResourceType.DOCUMENT,
        ".odp": ResourceType.DOCUMENT,
        # Archives
        ".zip": ResourceType.ARCHIVE,
        ".tar": ResourceType.ARCHIVE,
        ".gz": ResourceType.ARCHIVE,
        ".bz2": ResourceType.ARCHIVE,
        ".7z": ResourceType.ARCHIVE,
        ".rar": ResourceType.ARCHIVE,
    }

    # Content-Type mapping to resource types
    CONTENT_TYPE_MAP: Dict[str, ResourceType] = {
        # API / Data
        "application/json": ResourceType.API,
        "application/xml": ResourceType.API,
        "text/csv": ResourceType.DATASET,
        "text/xml": ResourceType.DATASET,
        # Images
        "image/jpeg": ResourceType.IMAGE,
        "image/png": ResourceType.IMAGE,
        "image/gif": ResourceType.IMAGE,
        "image/webp": ResourceType.IMAGE,
        "image/svg+xml": ResourceType.IMAGE,
        # Videos
        "video/mp4": ResourceType.VIDEO,
        "video/webm": ResourceType.VIDEO,
        "video/quicktime": ResourceType.VIDEO,
        # Audio
        "audio/mpeg": ResourceType.AUDIO,
        "audio/wav": ResourceType.AUDIO,
        "audio/ogg": ResourceType.AUDIO,
        # Documents
        "application/pdf": ResourceType.PDF,
        "application/msword": ResourceType.DOCUMENT,
        "application/vnd.openxmlformats-officedocument": ResourceType.DOCUMENT,
        # Archives
        "application/zip": ResourceType.ARCHIVE,
        "application/x-tar": ResourceType.ARCHIVE,
        "application/gzip": ResourceType.ARCHIVE,
        # Webpages (default)
        "text/html": ResourceType.WEBPAGE,
        "application/xhtml+xml": ResourceType.WEBPAGE,
    }

    # Open Graph type mapping
    OG_TYPE_MAP: Dict[str, ResourceType] = {
        "website": ResourceType.WEBPAGE,
        "article": ResourceType.WEBPAGE,
        "video.movie": ResourceType.VIDEO,
        "video.episode": ResourceType.VIDEO,
        "video.tv_show": ResourceType.VIDEO,
        "video.other": ResourceType.VIDEO,
        "music.song": ResourceType.AUDIO,
        "music.album": ResourceType.AUDIO,
        "music.playlist": ResourceType.AUDIO,
        "book": ResourceType.DOCUMENT,
    }

    def __init__(self, config: ResourceDetectorConfig):
        self.config = config
        self.url_patterns = self._compile_url_patterns()

    def _compile_url_patterns(self) -> Dict[ResourceType, list[Pattern]]:
        """Compile regex patterns for URL matching."""
        compiled = {}
        for resource_type, patterns in self.URL_PATTERNS.items():
            compiled[resource_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
        return compiled

    async def detect_resource_type(
        self,
        url: str,
        use_head_request: Optional[bool] = None,
        og_type: Optional[str] = None,
    ) -> ResourceTypeInfo:
        """
        Detect resource type using multiple strategies.

        Args:
            url: Target URL
            use_head_request: Override config for HEAD request (None = use config)
            og_type: Optional og:type from metadata (if already fetched)

        Returns:
            ResourceTypeInfo with detected type and enrichers
        """
        # Strategy 1: URL patterns + File extensions (FAST - no I/O)
        url_type_info = self._detect_from_url_pattern(url)
        ext_type_info = self._detect_from_file_extension(url)

        # Use result only if they agree and non-UNKNOWN, or exactly one is UNKNOWN
        if url_type_info.primary_type == ext_type_info.primary_type and url_type_info.primary_type != ResourceType.UNKNOWN:
            type_info = url_type_info
        elif ResourceType.UNKNOWN in (url_type_info.primary_type, ext_type_info.primary_type) and url_type_info.primary_type != ext_type_info.primary_type:
            type_info = url_type_info if url_type_info.primary_type != ResourceType.UNKNOWN else ext_type_info
        else:
            # Both UNKNOWN or both non-UNKNOWN but disagree - fall through
            type_info = None

        if type_info:
            logger.info(
                f"Detected resource type: {type_info.primary_type.value} "
                f"(method: {type_info.detection_method})"
            )
            return type_info

        # Fall through to more reliable strategies below

        # Strategy 2: Content-Type header (OPTIONAL - requires HEAD)
        should_use_head = (
            use_head_request
            if use_head_request is not None
            else self.config.enable_head_requests
        )
        if should_use_head:
            type_info = await self._detect_from_content_type(url)
            if type_info.primary_type != ResourceType.UNKNOWN:
                logger.info(
                    f"Detected resource type: {type_info.primary_type.value} "
                    f"(method: {type_info.detection_method})"
                )
                return type_info

        # Strategy 3: og:type (if provided)
        if og_type:
            type_info = self._detect_from_og_type(og_type)
            if type_info.primary_type != ResourceType.UNKNOWN:
                logger.info(
                    f"Detected resource type: {type_info.primary_type.value} "
                    f"(method: {type_info.detection_method})"
                )
                return type_info

        # Default to WEBPAGE
        type_info = ResourceTypeInfo(
            primary_type=ResourceType.WEBPAGE,
            detection_method="default",
        )

        logger.info(
            f"Detected resource type: {type_info.primary_type.value} "
            f"(method: {type_info.detection_method})"
        )

        return type_info

    def _detect_from_url_pattern(self, url: str) -> ResourceTypeInfo:
        """Detect resource type from URL patterns."""
        url_lower = url.lower()

        for resource_type, patterns in self.url_patterns.items():
            for pattern in patterns:
                if pattern.search(url_lower):
                    return ResourceTypeInfo(
                        primary_type=resource_type,
                        detection_method="url_pattern",
                    )

        # No pattern matched
        return ResourceTypeInfo(
            primary_type=ResourceType.UNKNOWN,
            detection_method="url_pattern",
        )

    def _detect_from_file_extension(self, url: str) -> ResourceTypeInfo:
        """Detect resource type from file extension."""
        try:
            parsed = urlparse(url)
            path = Path(parsed.path)
            extension = path.suffix.lower()

            if extension in self.EXTENSION_MAP:
                return ResourceTypeInfo(
                    primary_type=self.EXTENSION_MAP[extension],
                    detection_method="file_extension",
                )
        except Exception as e:
            logger.debug(f"Error parsing URL extension: {e}")

        # No extension matched
        return ResourceTypeInfo(
            primary_type=ResourceType.UNKNOWN,
            detection_method="file_extension",
        )

    async def _detect_from_content_type(self, url: str) -> ResourceTypeInfo:
        """Detect resource type from HTTP Content-Type header."""
        try:
            async with httpx.AsyncClient(
                timeout=self.config.head_request_timeout
            ) as client:
                response = await client.head(url, follow_redirects=True)
                content_type = response.headers.get("content-type", "").lower()

                # Extract base content type (before semicolon)
                base_content_type = content_type.split(";")[0].strip()

                # Check exact match
                if base_content_type in self.CONTENT_TYPE_MAP:
                    return ResourceTypeInfo(
                        primary_type=self.CONTENT_TYPE_MAP[base_content_type],
                        detection_method="content_type",
                    )

                # Check prefix match (e.g., "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                for ct_prefix, resource_type in self.CONTENT_TYPE_MAP.items():
                    if base_content_type.startswith(ct_prefix):
                        return ResourceTypeInfo(
                            primary_type=resource_type,
                            detection_method="content_type",
                        )

        except Exception as e:
            logger.debug(f"Error fetching Content-Type for {url}: {e}")

        # Failed to detect
        return ResourceTypeInfo(
            primary_type=ResourceType.UNKNOWN,
            detection_method="content_type",
        )

    def _detect_from_og_type(self, og_type: str) -> ResourceTypeInfo:
        """Detect resource type from Open Graph type."""
        og_type_lower = og_type.lower()

        if og_type_lower in self.OG_TYPE_MAP:
            return ResourceTypeInfo(
                primary_type=self.OG_TYPE_MAP[og_type_lower],
                detection_method="og_type",
            )

        # No match
        return ResourceTypeInfo(
            primary_type=ResourceType.UNKNOWN,
            detection_method="og_type",
        )
