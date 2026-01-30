from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, customers, vendors, catalog, tax_categories, templates, rfqs, quotes, invoices, units
from app.routers.internal import vendor_quotes

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "https://dev-b2b-quotation-system.vercel.app",
        "https://b2b-quotation-system.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",  # All Vercel preview domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Public Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(customers.router, prefix=f"{settings.API_V1_STR}/customers", tags=["customers"])
app.include_router(vendors.router, prefix=f"{settings.API_V1_STR}/vendors", tags=["vendors"])
app.include_router(catalog.router, prefix=f"{settings.API_V1_STR}/catalog-items", tags=["catalog"])
app.include_router(tax_categories.router, prefix=f"{settings.API_V1_STR}/tax-categories", tags=["tax-categories"])
app.include_router(templates.router, prefix=f"{settings.API_V1_STR}/templates", tags=["templates"])
app.include_router(rfqs.router, prefix=f"{settings.API_V1_STR}/rfqs", tags=["rfqs"])
app.include_router(quotes.router, prefix=f"{settings.API_V1_STR}/quotes", tags=["quotes"])
app.include_router(invoices.router, prefix=f"{settings.API_V1_STR}/invoices", tags=["invoices"])

# Internal Routers
app.include_router(vendor_quotes.router, prefix=f"{settings.API_V1_STR}/internal/vendor-quotes", tags=["internal"])

# Settings Routers
app.include_router(units.router, prefix=f"{settings.API_V1_STR}/settings/units", tags=["settings"])

# Auth Router (prefix is defined in the router itself)
app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "B2B Quotation System API", "status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
