"""
Request Logging Middleware
Logs request/response summaries with timing information.
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger
from app.core.request_id import get_request_id

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs request/response summaries.
    Includes method, path, status code, and duration.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        # Skip health check logging to reduce noise
        if request.url.path in ("/health", "/"):
            return await call_next(request)
        
        response = await call_next(request)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code}",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "request_id": get_request_id(),
                }
            }
        )
        
        return response
