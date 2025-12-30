from pydantic import BaseModel
from typing import Optional


class EnrichmentResult(BaseModel):
    """Result of metadata enrichment for a URL."""

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
