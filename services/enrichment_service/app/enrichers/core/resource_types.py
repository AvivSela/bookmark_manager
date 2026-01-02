"""Resource type definitions and data structures for enrichment."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Set


class ResourceType(str, Enum):
    """Enumeration of detectable resource types."""

    WEBPAGE = "webpage"  # Standard HTML pages
    API = "api"  # API endpoints
    DATASET = "dataset"  # Data files (CSV, JSON, XML)
    IMAGE = "image"  # Image files
    VIDEO = "video"  # Video files
    AUDIO = "audio"  # Audio files
    PDF = "pdf"  # PDF documents
    DOCUMENT = "document"  # Other documents (DOCX, etc.)
    ARCHIVE = "archive"  # ZIP, TAR, etc.
    CODE = "code"  # Source code repositories
    UNKNOWN = "unknown"  # Unable to determine


@dataclass
class ResourceTypeInfo:
    """Container for resource type detection information."""

    primary_type: ResourceType
    detection_method: str  # "url_pattern", "file_extension", "content_type", "og_type"
    applicable_enrichers: Set[str] = field(default_factory=set)
