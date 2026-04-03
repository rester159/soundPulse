#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head || echo "Migration warning (tables may already exist)"

echo "Seeding genre taxonomy..."
python scripts/seed_genres.py || echo "Genre seed warning (may already be seeded)"

echo "Starting SoundPulse API on port ${PORT:-8000}..."
exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
