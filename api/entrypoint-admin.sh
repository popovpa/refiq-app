#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting Admin API server..."
exec uvicorn app.admin.app:app --host 0.0.0.0 --port 8000 --workers 1
