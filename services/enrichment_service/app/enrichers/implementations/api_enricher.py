"""API enricher - detects and parses OpenAPI/Swagger specifications."""

import time
import httpx
import logging
import re
import yaml
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from app.enrichers.core.base_enricher import (
    BaseEnricher,
    EnricherContext,
    EnricherResult,
)
from app.enrichers.core.resource_types import ResourceType
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ApiEnricher(BaseEnricher):
    """Detect and parse OpenAPI/Swagger API specifications."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        # Parse spec paths from config
        self.spec_paths = [
            path.strip() for path in settings.api_spec_paths.split(",") if path.strip()
        ]

    async def enrich(self, context: EnricherContext) -> EnricherResult:
        """
        Enrich API by detecting and parsing OpenAPI/Swagger specs.

        Strategy:
        1. Try to find OpenAPI spec URL
        2. Fetch and parse spec (JSON or YAML)
        3. Extract key metadata
        4. Fallback to HTML scraping if no spec found

        Args:
            context: Enrichment context with URL and metadata

        Returns:
            EnricherResult with API metadata
        """
        start_time = time.time()

        try:
            # Step 1: Try to find OpenAPI spec
            spec_url = await self._find_openapi_spec(context.url)

            metadata = {}

            if spec_url:
                # Step 2: Fetch and parse spec
                spec = await self._fetch_spec(spec_url)
                if spec:
                    metadata = self._parse_openapi_spec(spec)
                    metadata["spec_url"] = spec_url

            # Step 3: Fallback to HTML scraping if enabled and no spec found
            if not metadata and settings.api_enable_html_fallback:
                metadata = await self._scrape_api_docs(context.url)

            execution_time = (time.time() - start_time) * 1000

            return EnricherResult(
                enricher=self,
                success=True,
                data={"api_metadata": metadata},
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(f"Failed to enrich API {context.url}: {e}")

            return EnricherResult(
                enricher=self,
                success=False,
                data={},
                error=str(e),
                execution_time_ms=execution_time,
            )

    async def _find_openapi_spec(self, url: str) -> Optional[str]:
        """
        Try common OpenAPI spec paths to find specification.

        Args:
            url: API URL

        Returns:
            Spec URL if found, None otherwise
        """
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        timeout = httpx.Timeout(5.0)  # Short timeout for spec detection
        headers = {"User-Agent": settings.user_agent}

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for path in self.spec_paths:
                spec_url = urljoin(base_url, path)

                try:
                    response = await client.head(spec_url)

                    if response.status_code == 200:
                        content_type = response.headers.get("content-type", "").lower()
                        # Accept JSON, YAML, or generic text/plain
                        if any(
                            ct in content_type
                            for ct in [
                                "json",
                                "yaml",
                                "text/plain",
                                "application/x-yaml",
                            ]
                        ):
                            self.logger.info(f"Found OpenAPI spec at {spec_url}")
                            return spec_url

                except Exception as e:
                    # Continue trying other paths
                    self.logger.debug(f"Failed to check {spec_url}: {e}")
                    continue

        self.logger.info(f"No OpenAPI spec found for {url}")
        return None

    async def _fetch_spec(self, spec_url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse OpenAPI spec (JSON or YAML).

        Args:
            spec_url: URL to OpenAPI specification

        Returns:
            Parsed spec dict or None
        """
        timeout = httpx.Timeout(settings.api_timeout_seconds)
        headers = {"User-Agent": settings.user_agent}

        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                response = await client.get(spec_url, headers=headers)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").lower()

                # Parse YAML or JSON based on content type or URL
                if "yaml" in content_type or spec_url.endswith((".yaml", ".yml")):
                    return yaml.safe_load(response.text)
                else:
                    return response.json()

        except Exception as e:
            self.logger.warning(f"Failed to fetch/parse spec from {spec_url}: {e}")
            return None

    def _parse_openapi_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from OpenAPI 3.x or Swagger 2.0 spec.

        Args:
            spec: Parsed OpenAPI/Swagger specification

        Returns:
            Dict with extracted metadata
        """
        metadata = {}

        try:
            # Detect spec version
            if "openapi" in spec:
                metadata["spec_version"] = spec["openapi"]  # "3.0.0", "3.1.0"
            elif "swagger" in spec:
                metadata["spec_version"] = f"swagger-{spec['swagger']}"  # "swagger-2.0"

            # Extract info section
            info = spec.get("info", {})
            metadata["api_title"] = info.get("title")
            metadata["api_version"] = info.get("version")
            metadata["description"] = info.get("description")

            # Extract base URL
            servers = spec.get("servers", [])
            if servers and isinstance(servers, list) and len(servers) > 0:
                metadata["base_url"] = servers[0].get("url")
            elif "host" in spec:  # Swagger 2.0
                schemes = spec.get("schemes", ["https"])
                scheme = schemes[0] if schemes else "https"
                base_path = spec.get("basePath", "")
                metadata["base_url"] = f"{scheme}://{spec['host']}{base_path}"

            # Count endpoints
            paths = spec.get("paths", {})
            endpoint_count = 0
            for path_methods in paths.values():
                if isinstance(path_methods, dict):
                    # Count HTTP methods, excluding special keys like 'parameters'
                    endpoint_count += len(
                        [
                            k
                            for k in path_methods.keys()
                            if k
                            not in ("parameters", "servers", "summary", "description")
                        ]
                    )
            metadata["endpoint_count"] = endpoint_count

            # Extract authentication methods
            auth_methods = self._extract_auth_methods(spec)
            if auth_methods:
                metadata["auth_methods"] = auth_methods

            # Extract tags
            tags = spec.get("tags", [])
            if tags:
                tag_names = [tag.get("name") for tag in tags if tag.get("name")]
                if tag_names:
                    metadata["tags"] = tag_names

        except Exception as e:
            self.logger.warning(f"Error parsing OpenAPI spec: {e}")

        return metadata

    def _extract_auth_methods(self, spec: Dict[str, Any]) -> List[str]:
        """
        Extract authentication methods from OpenAPI spec.

        Args:
            spec: Parsed OpenAPI/Swagger specification

        Returns:
            List of auth method types
        """
        auth_methods = []

        try:
            # OpenAPI 3.x
            security_schemes = spec.get("components", {}).get("securitySchemes", {})

            # Swagger 2.0
            if not security_schemes and "securityDefinitions" in spec:
                security_schemes = spec["securityDefinitions"]

            for scheme_name, scheme in security_schemes.items():
                if isinstance(scheme, dict):
                    auth_type = scheme.get("type", "")
                    if auth_type:
                        auth_methods.append(auth_type)

            # Deduplicate
            auth_methods = list(set(auth_methods))

        except Exception as e:
            self.logger.warning(f"Error extracting auth methods: {e}")

        return auth_methods

    async def _scrape_api_docs(self, url: str) -> Dict[str, Any]:
        """
        Fallback: Scrape API documentation page for basic metadata.

        Args:
            url: API documentation URL

        Returns:
            Dict with scraped metadata
        """
        timeout = httpx.Timeout(settings.api_timeout_seconds)
        headers = {"User-Agent": settings.user_agent}

        metadata = {}

        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")

                # Try to extract title
                title_tag = soup.find("h1")
                if title_tag:
                    metadata["api_title"] = title_tag.get_text(strip=True)

                # Try to find version in common patterns
                version_patterns = [
                    soup.find(
                        string=re.compile(r"Version\s*:?\s*[\d.]+", re.IGNORECASE)
                    ),
                    soup.find("span", class_=re.compile(r"version", re.IGNORECASE)),
                    soup.find("div", class_=re.compile(r"version", re.IGNORECASE)),
                ]

                for pattern in version_patterns:
                    if pattern:
                        version_match = re.search(r"[\d.]+", str(pattern))
                        if version_match:
                            metadata["api_version"] = version_match.group()
                            break

                # Try to extract description from meta tag
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    metadata["description"] = meta_desc["content"]

        except Exception as e:
            self.logger.warning(f"HTML scraping failed for {url}: {e}")

        return metadata

    def is_applicable(self, resource_type: ResourceType) -> bool:
        """
        ApiEnricher applies only to API resource types.

        Args:
            resource_type: Detected resource type

        Returns:
            True if resource is API
        """
        return resource_type == ResourceType.API

    @property
    def name(self) -> str:
        """Enricher name."""
        return "api"

    @property
    def required(self) -> bool:
        """ApiEnricher is optional (not required)."""
        return False

    @property
    def timeout(self) -> float:
        """Timeout for API enrichment."""
        return self.config.get("timeout", settings.api_timeout_seconds)
