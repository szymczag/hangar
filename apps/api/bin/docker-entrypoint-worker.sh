#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/docker-entrypoint-common.sh"

wait_for_database
wait_for_migrations
# Run the processes. The dedicated mail worker is the only worker that needs
# SES/SQS permissions; the default worker intentionally excludes that queue.
if [ "${HANGAR_WORKER_QUEUE:-default}" = "email" ]; then
    exec celery -A plane worker -l info -Q email -n email@%h
fi
if [ "${HANGAR_WORKER_QUEUE:-default}" = "imports" ]; then
    exec celery -A plane worker -l info -Q imports -n imports@%h \
        --concurrency="${TODOIST_IMPORT_WORKER_CONCURRENCY:-2}" \
        --prefetch-multiplier="${TODOIST_IMPORT_WORKER_PREFETCH_MULTIPLIER:-1}"
fi
exec celery -A plane worker -l info -Q celery
