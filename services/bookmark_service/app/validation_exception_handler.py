import logging
from fastapi import Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with detailed error messages.

    Transforms Pydantic validation errors into properly formatted HTTP 400 responses
    with detailed field-level error information.
    """
    errors = []
    for error in exc.errors():
        error_dict = {
            "loc": list(error.get("loc", [])),
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        # Add input if it exists
        if "input" in error:
            error_dict["input"] = str(error["input"])
        errors.append(error_dict)

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": errors}
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with structured logging and request correlation.

    Logs HTTP exceptions with context (request ID, method, path, status code)
    and includes X-Request-ID header in error responses for request tracing.
    """
    # Get request ID from middleware
    request_id = getattr(request.state, "request_id", "unknown")

    # Log with appropriate level based on status code
    log_message = (
        f"HTTP exception: status_code={exc.status_code} "
        f"detail={exc.detail} path={request.url.path} "
        f"method={request.method} request_id={request_id}"
    )

    if exc.status_code >= 500:
        logger.error(log_message)
    else:
        logger.warning(log_message)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"X-Request-ID": request_id},
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unexpected exceptions with generic error message."""
    # Get request ID if available
    request_id = getattr(request.state, "request_id", None)

    # Log detailed error server-side with structured logging
    logger.error(
        "Unexpected error occurred",
        extra={
            "error": str(exc),
            "error_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method,
            "request_id": request_id,
        },
        exc_info=True,
    )

    # Return generic error to client (no sensitive information)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

    # Add request ID to error response
    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response
