"""Prometheus metrics for validation service."""

import logging
from typing import Callable

from fastapi import FastAPI
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

logger = logging.getLogger(__name__)

# HTTP metrics (automatically collected by instrumentator)
# - http_requests_total
# - http_request_duration_seconds

# Validation metrics
validation_results_total = Counter(
    "validation_results_total",
    "Total number of validation results",
    ["result"],  # valid, invalid, error
)

validation_duration_seconds = Histogram(
    "validation_duration_seconds",
    "URL validation duration in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

validation_attempts = Histogram(
    "validation_attempts",
    "Number of validation attempts per bookmark",
    buckets=[1, 2, 3, 4, 5, 10, 20],
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

# Kafka producer metrics
kafka_events_published_total = Counter(
    "kafka_events_published_total",
    "Total number of Kafka events published",
    ["event_type", "status"],
)

# HTTP client metrics (bookmark service API calls)
http_client_requests_total = Counter(
    "http_client_requests_total",
    "Total number of HTTP client requests",
    ["method", "service", "status_code"],
)

http_client_request_duration_seconds = Histogram(
    "http_client_request_duration_seconds",
    "HTTP client request duration in seconds",
    ["method", "service"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Scheduler metrics
scheduler_jobs_executed_total = Counter(
    "scheduler_jobs_executed_total",
    "Total number of scheduler jobs executed",
    ["job_name", "status"],
)

scheduler_job_duration_seconds = Histogram(
    "scheduler_job_duration_seconds",
    "Scheduler job duration in seconds",
    ["job_name"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
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


def record_validation_result(result: str, duration: float | None = None) -> None:
    """
    Record a validation result metric.

    Args:
        result: Validation result (valid, invalid, error)
        duration: Optional validation duration in seconds
    """
    validation_results_total.labels(result=result).inc()

    if duration is not None:
        validation_duration_seconds.observe(duration)


def record_validation_attempts(attempts: int) -> None:
    """
    Record the number of validation attempts.

    Args:
        attempts: Number of attempts
    """
    validation_attempts.observe(attempts)


def record_kafka_message(topic: str, status: str = "success") -> None:
    """
    Record a Kafka message consumption metric.

    Args:
        topic: Topic name
        status: Consumption status (success, error)
    """
    kafka_messages_consumed_total.labels(topic=topic, status=status).inc()


def record_kafka_event(event_type: str, status: str = "success") -> None:
    """
    Record a Kafka event publication metric.

    Args:
        event_type: Event type (validation.completed, etc.)
        status: Publication status (success, error)
    """
    kafka_events_published_total.labels(event_type=event_type, status=status).inc()


def record_http_client_request(
    method: str, service: str, status_code: int, duration: float
) -> None:
    """
    Record an HTTP client request metric.

    Args:
        method: HTTP method (GET, POST, etc.)
        service: Target service name
        status_code: HTTP status code
        duration: Request duration in seconds
    """
    http_client_requests_total.labels(
        method=method, service=service, status_code=status_code
    ).inc()
    http_client_request_duration_seconds.labels(method=method, service=service).observe(
        duration
    )


def record_scheduler_job(job_name: str, status: str, duration: float) -> None:
    """
    Record a scheduler job execution metric.

    Args:
        job_name: Job name
        status: Execution status (success, error)
        duration: Job duration in seconds
    """
    scheduler_jobs_executed_total.labels(job_name=job_name, status=status).inc()
    scheduler_job_duration_seconds.labels(job_name=job_name).observe(duration)


def track_validation_time() -> Callable:
    """
    Decorator to track validation execution time.

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            with validation_duration_seconds.time():
                return await func(*args, **kwargs)

        return wrapper

    return decorator
