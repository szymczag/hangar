#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/docker-entrypoint-common.sh"

if [[ $# -gt 0 ]]; then
    wait_for_database "$1"
    python manage.py migrate "$1"
else
    wait_for_database
    python manage.py migrate
fi
