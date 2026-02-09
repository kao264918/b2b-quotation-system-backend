"""
Request ID Middleware
Generates a unique request ID for each request and adds it to the response headers.
"""
import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variable to store the current request ID
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Get the current request ID from context."""
    return request_id_ctx.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates a unique request ID for each incoming request.
    The ID is stored in a context variable and added to response headers.
    """

    async def dispatch(self, request: Request, call_next):
        # Check if client provided a request ID, otherwise generate one
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        # Store in context for logging access
        token = request_id_ctx.set(request_id)
        
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)
