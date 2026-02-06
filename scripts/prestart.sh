#!/bin/bash
# prestart.sh - Run database migrations before starting the application
# This script is intended for Railway deployment or similar environments.
#
# Usage:
#   Option 1 (Railway): Set as a separate deploy command
#   Option 2 (Docker): Use as entrypoint before uvicorn
#
# Example Docker CMD:
#   CMD ["sh", "-c", "./scripts/prestart.sh && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

set -e

echo "Running database migrations..."
alembic upgrade head
echo "Migrations completed successfully."
