#!/bin/bash
set -e

echo "� Running database migrations..."
alembic upgrade head

echo "�🔧 Initializing admin user..."
python init_admin.py || true

echo "🚀 Starting backend server..."
exec "$@"
