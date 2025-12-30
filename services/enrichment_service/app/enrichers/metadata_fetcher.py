import httpx
from bs4 import BeautifulSoup
from typing import Optional
import logging
from urllib.parse import urljoin, urlparse
from app.schemas.enrichment import EnrichmentResult
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MetadataFetcher:
    """Fetch and extract metadata from URLs."""

    def __init__(self):
        self.timeout = httpx.Timeout(settings.enrichment_timeout_seconds)
        self.headers = {
            'User-Agent': settings.user_agent,
            'Accept': 'text/html,application/xhtml+xml',
        }

    async def fetch_metadata(self, url: str) -> EnrichmentResult:
        """
        Fetch URL and extract metadata.

        Returns EnrichmentResult with extracted fields.
        Raises httpx exceptions on network errors.
        """
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()

            # Only process HTML responses
            content_type = response.headers.get('content-type', '')
            if 'html' not in content_type.lower():
                raise ValueError(f"Non-HTML content type: {content_type}")

            html = response.text
            soup = BeautifulSoup(html, 'lxml')

            # Extract Open Graph tags
            og_title = self._get_meta_tag(soup, 'og:title')
            og_description = self._get_meta_tag(soup, 'og:description')
            og_image = self._get_meta_tag(soup, 'og:image')
            og_type = self._get_meta_tag(soup, 'og:type')
            og_site_name = self._get_meta_tag(soup, 'og:site_name')

            # Extract standard meta tags (fallback)
            meta_description = self._get_meta_tag(soup, 'description', property_attr='name')

            # Extract favicon
            favicon_url = self._get_favicon(soup, url)

            # Make og_image and favicon absolute URLs
            if og_image:
                og_image = urljoin(url, og_image)
            if favicon_url:
                favicon_url = urljoin(url, favicon_url)

            return EnrichmentResult(
                og_title=og_title,
                og_description=og_description,
                og_image=og_image,
                og_type=og_type,
                og_site_name=og_site_name,
                meta_description=meta_description,
                favicon_url=favicon_url
            )

    def _get_meta_tag(
        self,
        soup: BeautifulSoup,
        property_value: str,
        property_attr: str = 'property'
    ) -> Optional[str]:
        """Extract meta tag content by property/name attribute."""
        tag = soup.find('meta', {property_attr: property_value})
        return tag.get('content') if tag else None

    def _get_favicon(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract favicon URL with fallback logic."""
        # Try <link rel="icon">
        icon_link = soup.find('link', rel=lambda x: x and 'icon' in x.lower() if x else False)
        if icon_link and icon_link.get('href'):
            return icon_link['href']

        # Fallback: /favicon.ico
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
