#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/docker-entrypoint-common.sh"

wait_for_database
wait_for_migrations

export MACHINE_SIGNATURE="${MACHINE_SIGNATURE:-hangar-self-managed}"

# Register instance
python manage.py register_instance "$MACHINE_SIGNATURE"

# Load the configuration variable
python manage.py configure_instance

# Create the default bucket
python manage.py create_bucket

# Clear Cache before starting to remove stale values
python manage.py clear_cache

# Collect static files
python manage.py collectstatic --noinput

exec gunicorn -w "${GUNICORN_WORKERS:-2}" -k uvicorn.workers.UvicornWorker plane.asgi:application --bind 0.0.0.0:"${PORT:-8000}" --max-requests 1200 --max-requests-jitter 1000 --access-logfile -
