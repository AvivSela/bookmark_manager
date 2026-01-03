"""Prometheus metrics for enrichment service."""

import logging
from typing import Callable

from fastapi import FastAPI
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

logger = logging.getLogger(__name__)

# HTTP metrics (automatically collected by instrumentator)
# - http_requests_total
# - http_request_duration_seconds

# Enrichment processing metrics
enrichment_processed_total = Counter(
    "enrichment_processed_total",
    "Total number of enrichments processed",
    ["enricher_type", "status"],
)

enrichment_duration_seconds = Histogram(
    "enrichment_duration_seconds",
    "Enrichment processing duration in seconds",
    ["enricher_type"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

# Kafka consumer metrics
kafka_consumer_lag = Counter(
    "kafka_consumer_lag_total",
    "Kafka consumer lag (messages behind)",
    ["topic", "partition"],
)

kafka_messages_consumed_total = Counter(
    "kafka_messages_consumed_total",
    "Total number of Kafka messages consumed",
    ["topic", "status"],
)

# HTTP client metrics (external API calls)
http_client_requests_total = Counter(
    "http_client_requests_total",
    "Total number of HTTP client requests",
    ["method", "host", "status_code"],
)

http_client_request_duration_seconds = Histogram(
    "http_client_request_duration_seconds",
    "HTTP client request duration in seconds",
    ["method", "host"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# Retry metrics
enrichment_retries_total = Counter(
    "enrichment_retries_total",
    "Total number of enrichment retries",
    ["enricher_type", "attempt"],
)


def setup_metrics(app: FastAPI, app_name: str, app_version: str) -> None:
    """
    Setup Prometheus metrics instrumentation for FastAPI app.

    Args:
        app: FastAPI application instance
        app_name: Application name
        app_version: Application version
    """
    # Instrument FastAPI with Prometheus metrics
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    # Add custom info metric
    instrumentator.add(
        lambda metrics: metrics.info(
            "app_info",
            "Application information",
            version=app_version,
            app_name=app_name,
        )
    )

    # Instrument the app and expose /metrics endpoint
    instrumentator.instrument(app).expose(app, include_in_schema=False)

    logger.info("Prometheus metrics enabled at /metrics")


def record_enrichment(
    enricher_type: str, status: str, duration: float | None = None
) -> None:
    """
    Record an enrichment operation metric.

    Args:
        enricher_type: Type of enricher (metadata, favicon, screenshot, etc.)
        status: Operation status (success, error, skipped)
        duration: Optional duration in seconds
    """
    enrichment_processed_total.labels(enricher_type=enricher_type, status=status).inc()

    if duration is not None:
        enrichment_duration_seconds.labels(enricher_type=enricher_type).observe(
            duration
        )


def record_kafka_message(topic: str, status: str = "success") -> None:
    """
    Record a Kafka message consumption metric.

    Args:
        topic: Topic name
        status: Consumption status (success, error)
    """
    kafka_messages_consumed_total.labels(topic=topic, status=status).inc()


def record_http_client_request(
    method: str, host: str, status_code: int, duration: float
) -> None:
    """
    Record an HTTP client request metric.

    Args:
        method: HTTP method (GET, POST, etc.)
        host: Target host
        status_code: HTTP status code
        duration: Request duration in seconds
    """
    http_client_requests_total.labels(
        method=method, host=host, status_code=status_code
    ).inc()
    http_client_request_duration_seconds.labels(method=method, host=host).observe(
        duration
    )


def record_retry(enricher_type: str, attempt: int) -> None:
    """
    Record a retry attempt metric.

    Args:
        enricher_type: Type of enricher
        attempt: Retry attempt number
    """
    enrichment_retries_total.labels(
        enricher_type=enricher_type, attempt=str(attempt)
    ).inc()


def track_enrichment_time(enricher_type: str) -> Callable:
    """
    Decorator to track enrichment execution time.

    Args:
        enricher_type: Type of enricher

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            with enrichment_duration_seconds.labels(
                enricher_type=enricher_type
            ).time():
                return await func(*args, **kwargs)

        return wrapper

    return decorator
