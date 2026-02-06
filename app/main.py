import re

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.deps.auth import get_current_user, require_superuser
from app.routers import auth, customers, vendors, catalog, tax_categories, templates, rfqs, quotes, invoices, units
from app.routers.internal import vendor_quotes
from app.core.request_id import RequestIdMiddleware
from app.core.request_logging import RequestLoggingMiddleware
from app.core.logging import setup_logging

is_production = settings.ENVIRONMENT == "production"

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

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PATHS = {
    f"{settings.API_V1_STR}/auth/login",
    f"{settings.API_V1_STR}/auth/forgot-password",
    f"{settings.API_V1_STR}/auth/reset-password",
    f"{settings.API_V1_STR}/auth/set-password",
    f"{settings.API_V1_STR}/auth/request-access",
}
ALLOWED_ORIGIN_REGEX = re.compile(r"https://.*\.vercel\.app")


def is_allowed_origin(origin: str) -> bool:
    if origin in settings.CORS_ORIGINS:
        return True
    if settings.APP_BASE_URL and origin == settings.APP_BASE_URL:
        return True
    return bool(ALLOWED_ORIGIN_REGEX.match(origin))


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    if request.method in UNSAFE_METHODS and request.url.path.startswith(settings.API_V1_STR):
        if request.url.path not in CSRF_EXEMPT_PATHS:
            origin = request.headers.get("origin")
            if origin and not is_allowed_origin(origin):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Origin not allowed"},
                )

            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("x-csrf-token")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token missing or invalid"},
                )

    return await call_next(request)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",  # All Vercel preview domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-Id"],
)

# Observability Middleware (order matters: RequestId runs first, then Logging)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIdMiddleware)

# Public Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
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



@app.get("/")
def root():
    return {"message": "B2B Quotation System API", "status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
