"""FastAPI middleware for request correlation ID tracking and structured logging."""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.common.logging import get_logger, set_request_id

logger = get_logger("common.middleware")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns or extracts a correlation Request ID for every HTTP request.

    - Inspects incoming headers: 'X-Request-ID', 'X-Correlation-ID', or creates a new UUID.
    - Sets the request ID into the async ContextVar so all downstream loggers include it.
    - Adds the 'X-Request-ID' header to the response.
    - Logs request initiation and completion with latency.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # Extract correlation ID from headers or generate new one
        correlation_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or f"req_{uuid.uuid4().hex[:12]}"
        )

        # Set in request state and async context
        request.state.request_id = correlation_id
        set_request_id(correlation_id)

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            response.headers["X-Request-ID"] = correlation_id
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"Unhandled exception processing {request.method} {request.url.path} after {duration_ms:.2f}ms: {exc}",
                exc_info=True,
            )
            raise
        finally:
            # Clean up context to prevent leakage across pooled worker tasks
            set_request_id(None)
