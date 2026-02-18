import logging
import re

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.deps.auth import get_current_user, require_superuser
from app.routers import auth, customers, vendors, catalog, tax_categories, templates, rfqs, quotes, invoices, units
from app.routers.internal import vendor_quotes
from app.core.request_id import RequestIdMiddleware, get_request_id
from app.core.request_logging import RequestLoggingMiddleware
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)

is_production = settings.ENVIRONMENT == "production"

# ---------------------------------------------------------------------------
# Sentry Error Tracking (optional, requires SENTRY_DSN env var)
# ---------------------------------------------------------------------------
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1 if is_production else 1.0,
            send_default_pii=False,
        )
        logger.info("Sentry initialized successfully")
    except Exception as e:
        logger.warning("Failed to initialize Sentry: %s", e)

# Initialize structured logging
setup_logging(
    log_level="INFO",
    json_format=is_production,  # JSON in production, standard format in dev
)

if is_production and settings.SECRET_KEY.startswith("CHANGE_THIS"):
    raise RuntimeError("SECRET_KEY must be set to a secure value in production.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=None if is_production else f"{settings.API_V1_STR}/openapi.json",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
)


# ---------------------------------------------------------------------------
# Global unhandled exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PATHS = {
    f"{settings.API_V1_STR}/auth/login",
    f"{settings.API_V1_STR}/auth/logout",
    f"{settings.API_V1_STR}/auth/forgot-password",
    f"{settings.API_V1_STR}/auth/reset-password",
    f"{settings.API_V1_STR}/auth/set-password",
    f"{settings.API_V1_STR}/auth/request-access",
}

# Build origin regex from config (scoped to YOUR Vercel project, not all *.vercel.app)
ALLOWED_ORIGIN_REGEX = (
    re.compile(settings.CORS_ORIGIN_REGEX)
    if settings.CORS_ORIGIN_REGEX
    else None
)


def is_allowed_origin(origin: str) -> bool:
    if origin in settings.CORS_ORIGINS:
        return True
    if settings.APP_BASE_URL and origin == settings.APP_BASE_URL:
        return True
    if ALLOWED_ORIGIN_REGEX and ALLOWED_ORIGIN_REGEX.fullmatch(origin):
        return True
    return False


def log_security_event(event: str, request: Request, detail: str, origin: str | None = None) -> None:
    logger.warning(
        event,
        extra={
            "extra_fields": {
                "event": event,
                "detail": detail,
                "method": request.method,
                "path": request.url.path,
                "origin": origin,
                "request_id": get_request_id(),
            }
        },
    )


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    if request.method == "OPTIONS" and request.url.path.startswith(settings.API_V1_STR):
        origin = request.headers.get("origin")
        response = await call_next(request)
        if response.status_code >= 400:
            log_security_event(
                "cors_preflight_rejected",
                request,
                f"preflight returned {response.status_code}",
                origin=origin,
            )
        return response

    if request.method in UNSAFE_METHODS and request.url.path.startswith(settings.API_V1_STR):
        if request.url.path not in CSRF_EXEMPT_PATHS:
            origin = request.headers.get("origin")
            if origin and not is_allowed_origin(origin):
                log_security_event(
                    "origin_rejected",
                    request,
                    "Origin is not in allowlist",
                    origin=origin,
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Origin not allowed"},
                )

            # Stateless CSRF: For cross-site, browser can't read cookies.
            # We rely on the Origin header check above + require a token header.
            # The token proves the request came from JS that called /csrf first.
            csrf_header = request.headers.get("x-csrf-token")
            if not csrf_header:
                log_security_event(
                    "csrf_rejected",
                    request,
                    "Missing X-CSRF-Token header",
                    origin=origin,
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token missing or invalid"},
                )

    return await call_next(request)


# ---------------------------------------------------------------------------
# CORS Configuration — only allow configured origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,  # None disables regex matching
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-Id"],
)

# Observability Middleware (order matters: RequestId runs first, then Logging)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIdMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Public Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
from app.routers import registration
app.include_router(registration.router, prefix=f"{settings.API_V1_STR}", tags=["registration"])
app.include_router(
    customers.router,
    prefix=f"{settings.API_V1_STR}/customers",
    tags=["customers"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    vendors.router,
    prefix=f"{settings.API_V1_STR}/vendors",
    tags=["vendors"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    catalog.router,
    prefix=f"{settings.API_V1_STR}/catalog-items",
    tags=["catalog"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    tax_categories.router,
    prefix=f"{settings.API_V1_STR}/tax-categories",
    tags=["tax-categories"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    templates.router,
    prefix=f"{settings.API_V1_STR}/templates",
    tags=["templates"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    rfqs.router,
    prefix=f"{settings.API_V1_STR}/rfqs",
    tags=["rfqs"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    quotes.router,
    prefix=f"{settings.API_V1_STR}/quotes",
    tags=["quotes"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    invoices.router,
    prefix=f"{settings.API_V1_STR}/invoices",
    tags=["invoices"],
    dependencies=[Depends(get_current_user)],
)

# Internal Routers
app.include_router(
    vendor_quotes.router,
    prefix=f"{settings.API_V1_STR}/internal/vendor-quotes",
    tags=["internal"],
    dependencies=[Depends(require_superuser)],
)

# Settings Routers
app.include_router(
    units.router,
    prefix=f"{settings.API_V1_STR}/settings/units",
    tags=["settings"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Health / Root
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "B2B Quotation System API", "status": "ok"}


@app.get("/health")
def health_check():
    """
    Health check that verifies database connectivity.
    Returns 503 if the database is unreachable.
    """
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        logger.exception("Health check failed: database unreachable")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "detail": "database unreachable"},
        )
    return {"status": "healthy"}
