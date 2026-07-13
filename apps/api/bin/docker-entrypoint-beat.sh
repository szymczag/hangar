#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/docker-entrypoint-common.sh"

wait_for_database
wait_for_migrations
# Run the processes
celery -A plane beat -l info
