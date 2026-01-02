from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EnrichmentResult(BaseModel):
    """Result of metadata enrichment for a URL."""

    # ===== EXISTING FIELDS (Backward Compatible) =====
    # Open Graph metadata
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: Optional[str] = None
    og_site_name: Optional[str] = None

    # Standard meta tags (fallback)
    meta_description: Optional[str] = None

    # Favicon
    favicon_url: Optional[str] = None

    # ===== NEW FIELDS (Enrichment v2) =====
    # Resource type detection
    resource_type: Optional[str] = Field(
        None,
        description="Detected resource type: webpage, api, dataset, image, video, etc.",
    )

    # Screenshot enhancement (Phase 2 - not yet implemented)
    screenshot_url: Optional[str] = Field(
        None, description="URL to screenshot image of the webpage"
    )

    # Type-specific metadata (stored as JSON in DB)
    api_metadata: Optional[Dict[str, Any]] = Field(
        None, description="API-specific fields: api_spec_url, api_title, etc."
    )

    dataset_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Dataset-specific fields: format, schema, column_count, etc."
    )

    media_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Media-specific fields: dimensions, duration, codec, etc.",
    )
