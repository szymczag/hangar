#!/bin/bash

set -euo pipefail

validate_timeout() {
    local value="$1"
    local name="$2"

    if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
        echo "$name must be a positive integer, got: $value" >&2
        exit 64
    fi
}

wait_for_database() {
    local timeout_seconds="${DEPENDENCY_WAIT_TIMEOUT_SECONDS:-300}"
    validate_timeout "$timeout_seconds" "DEPENDENCY_WAIT_TIMEOUT_SECONDS"
    timeout "$timeout_seconds" python manage.py wait_for_db "$@"
}

wait_for_migrations() {
    local timeout_seconds="${MIGRATION_WAIT_TIMEOUT_SECONDS:-600}"
    validate_timeout "$timeout_seconds" "MIGRATION_WAIT_TIMEOUT_SECONDS"
    timeout "$timeout_seconds" python manage.py wait_for_migrations
}
