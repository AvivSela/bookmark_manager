"""Enricher implementations for different resource types."""

from app.enrichers.implementations.api_enricher import ApiEnricher
from app.enrichers.implementations.dataset_enricher import DatasetEnricher
from app.enrichers.implementations.image_enricher import ImageEnricher
from app.enrichers.implementations.webpage_enricher import WebPageEnricher

__all__ = [
    "ApiEnricher",
    "DatasetEnricher",
    "ImageEnricher",
    "WebPageEnricher",
]
