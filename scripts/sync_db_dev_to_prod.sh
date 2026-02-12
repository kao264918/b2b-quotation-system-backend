#!/bin/bash

# Database Sync Script: Dev -> Prod
# STRICTLY for copying development data to production.
# WARNING: This will overwrite the target database.

set -e

# Check for required tools
if ! command -v pg_dump &> /dev/null; then
    echo "Error: pg_dump is not installed or not in PATH."
    exit 1
fi

if ! command -v psql &> /dev/null; then
    echo "Error: psql is not installed or not in PATH."
    exit 1
fi

echo "========================================================"
echo "      DATABASE SYNC: DEVELOPMENT -> PRODUCTION"
echo "========================================================"
echo "WARNING: This script will WIPE the PRODUCTION database"
echo "and replace it with a copy of the DEVELOPMENT database."
echo "========================================================"
echo ""

# Prompt for Database URLs if not set in environment
if [ -z "$DEV_DB_URL" ]; then
    read -p "Enter DEVELOPMENT Database URL (source): " DEV_DB_URL
fi

if [ -z "$PROD_DB_URL" ]; then
    read -p "Enter PRODUCTION Database URL (target): " PROD_DB_URL
fi

if [ -z "$DEV_DB_URL" ] || [ -z "$PROD_DB_URL" ]; then
    echo "Error: Both Database URLs are required."
    exit 1
fi

echo ""
echo "Source: $DEV_DB_URL"
echo "Target: $PROD_DB_URL"
echo ""
echo "Are you ABSOLUTELY SURE you want to proceed?"
read -p "Type 'confirmoverwrite' to continue: " CONFIRM

if [ "$CONFIRM" != "confirmoverwrite" ]; then
    echo "Operation cancelled."
    exit 0
fi

echo ""
echo "Starting synchronization..."
echo "1. Dumping source database..."
echo "2. Piping to target database..."

# Perform the dump and restore
# --no-owner --no-acl: Skip ownership/privilege commands to avoid errors on managed DBs
# -c: Clean (drop) database objects before creating them
# --if-exists: Use IF EXISTS when dropping objects
pg_dump "$DEV_DB_URL" --no-owner --no-acl -c --if-exists | psql "$PROD_DB_URL"

echo ""
echo "========================================================"
echo "      SYNCHRONIZATION COMPLETE"
echo "========================================================"
