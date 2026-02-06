# Dockerfile for B2B Quotation System Backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libreoffice \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run migration and start server.
# --forwarded-allow-ips: In production, restrict to your load balancer's IP range.
# Using '*' only when behind a trusted reverse proxy (e.g., Railway).
# Override via FORWARDED_ALLOW_IPS env var for tighter control.
CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '${FORWARDED_ALLOW_IPS:-*}'"
