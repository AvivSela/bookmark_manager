"""Prometheus metrics for bookmark service."""

import logging
from typing import Callable

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

logger = logging.getLogger(__name__)

HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total', 
    'Total number of HTTP requests', 
    ['method', 'endpoint', 'service']
)

# HTTP metrics (automatically collected by instrumentator)
# - http_requests_total
# - http_request_duration_seconds

# Business operation metrics
bookmark_operations_total = Counter(
    "bookmark_operations_total",
    "Total number of bookmark CRUD operations",
    ["operation", "tenant_id", "status"],
)

# Kafka metrics
kafka_events_published_total = Counter(
    "kafka_events_published_total",
    "Total number of Kafka events published",
    ["event_type", "status"],
)

# Database metrics
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

db_connection_pool_size = Gauge(
    "db_connection_pool_size",
    "Database connection pool size",
)

db_connection_pool_checked_out = Gauge(
    "db_connection_pool_checked_out",
    "Number of checked out connections",
)

db_connection_pool_overflow = Gauge(
    "db_connection_pool_overflow",
    "Number of overflow connections",
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


async def collect_db_pool_metrics() -> None:
    """Collect database connection pool metrics."""
    from app.database import engine

    pool = engine.pool

    # Get pool statistics
    db_connection_pool_size.set(pool.size())
    db_connection_pool_checked_out.set(pool.checkedout())
    db_connection_pool_overflow.set(pool.overflow())


def record_bookmark_operation(
    operation: str, tenant_id: str, status: str = "success"
) -> None:
    """
    Record a bookmark operation metric.

    Args:
        operation: Operation type (create, read, update, delete, list)
        tenant_id: Tenant ID
        status: Operation status (success, error)
    """
    bookmark_operations_total.labels(
        operation=operation, tenant_id=tenant_id, status=status
    ).inc()


def record_kafka_event(event_type: str, status: str = "success") -> None:
    """
    Record a Kafka event publication metric.

    Args:
        event_type: Event type (bookmark.created, bookmark.updated, etc.)
        status: Publication status (success, error)
    """
    kafka_events_published_total.labels(event_type=event_type, status=status).inc()


def track_db_query_time(query_type: str) -> Callable:
    """
    Decorator to track database query execution time.

    Args:
        query_type: Type of query (select, insert, update, delete)

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            with db_query_duration_seconds.labels(query_type=query_type).time():
                return await func(*args, **kwargs)

        return wrapper

    return decorator
