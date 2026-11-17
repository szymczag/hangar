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

# Published template values. Must match _INSECURE_SECRET_KEYS in
# plane/settings/common.py (a test compares the two).
INSECURE_SECRET_KEYS=(
    "60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5"
    "change-this-key-on-deployment"
)

# Django signs sessions, password-reset links and CSRF tokens with SECRET_KEY,
# and encrypts the instance settings saved in God Mode with it. A published
# value lets anybody forge those, and an empty one makes every container pick
# its own random key, so a session signed by one is rejected by the next.
# HANGAR_ALLOW_INSECURE_DEFAULTS=1 lets a throwaway development stack start
# anyway; never set it on a deployment anybody else can reach.
require_secret_key() {
    if [[ "${HANGAR_ALLOW_INSECURE_DEFAULTS:-0}" == "1" ]]; then
        return 0
    fi
    local value="${SECRET_KEY:-}" insecure
    if [[ -z "$value" ]]; then
        echo "SECRET_KEY is empty. Set a long random value (for example: openssl rand -hex 32); the Compose installer generates one." >&2
        exit 64
    fi
    for insecure in "${INSECURE_SECRET_KEYS[@]}"; do
        if [[ "$value" == "$insecure" ]]; then
            echo "SECRET_KEY is a published template value. Replace it with a long random value (for example: openssl rand -hex 32); the Compose installer does this on upgrade. Everybody is signed out once." >&2
            exit 64
        fi
    done
}

require_secret_key
