#!/usr/bin/env bash
# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.
#
# Qualifies the Docker Compose upgrade and restore path the way an operator
# walks it:
#
#   1. install the previous stable release with its own setup.sh and release
#      assets, and start it;
#   2. seed it (compose_seed.py) and record a fingerprint of the data;
#   3. back it up with `setup.sh backup`, keeping plane.env beside the archives;
#   4. upgrade with the candidate's installer and Compose file
#      (`setup.sh --yes upgrade`) to the candidate images, start, and check the
#      fingerprint, a password sign-in through the proxy and an API-key call;
#   5. remove the deployment with its volumes, restore the backup into a fresh
#      directory with restore.sh, start it with the candidate, and check again.
#
# Usage: compose-upgrade.sh --to <image tag> [--from <release tag>]
#
#   --to     image tag of the candidate, e.g. v0.2.0 or preview-sha-<commit>
#   --from   release to upgrade from, e.g. hangar-v0.1.0 (default: the latest
#            stable GitHub Release; prereleases are never chosen)
#
# Environment:
#   WORK_DIR             where the deployments live (default: a new temp dir)
#   ARTIFACT_DIR         fingerprints, backup and logs (default: $WORK_DIR/artifacts)
#   HTTP_PORT            host port of the proxy (default 18080); HTTPS uses +1
#   SOURCE_DIR           candidate deployments/cli/community (default: this checkout)
#   GITHUB_REPOSITORY    owner/name to take releases from (default szymczag/hangar)
#   GH_TOKEN             used with gh to find the latest release when --from is omitted
#   KEEP_DEPLOYMENT=1    leave the last deployment running at the end
#
# The installer names the Compose project after its folder, plane-app, and
# restore.sh only restores plane-app_* volumes, so the script refuses to run
# while any plane-app container or volume exists on the Docker host. Run it on
# a CI runner or a container engine of its own.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
SEED_SCRIPT="$SCRIPT_DIR/compose_seed.py"
SOURCE_DIR=${SOURCE_DIR:-$REPO_ROOT/deployments/cli/community}
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-szymczag/hangar}
HTTP_PORT=${HTTP_PORT:-18080}
HTTPS_PORT=$((HTTP_PORT + 1))
BASE_URL="http://localhost:$HTTP_PORT"
PROJECT=plane-app
ADMIN_EMAIL=admin@upgrade.hangar.invalid
TEMPLATE_SECRET_KEYS=" 60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5 change-this-key-on-deployment "
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-900}

FROM_RELEASE=""
TO_IMAGE_TAG=""
CURRENT_DEPLOYMENT=""
PHASE=setup

log() { printf '\n==> %s\n' "$*"; }
fail() {
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
        printf '::error::%s\n' "$*"
    else
        printf 'ERROR: %s\n' "$*" >&2
    fi
    exit 1
}

usage() {
    sed -n '/^# Usage:/,/^# Environment:/p' "$0" | sed '$d; s/^# \{0,1\}//'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --from) FROM_RELEASE=${2:-}; shift 2 ;;
        --to) TO_IMAGE_TAG=${2:-}; shift 2 ;;
        -h|--help) usage 0 ;;
        *) echo "Unknown argument: $1" >&2; usage 2 ;;
    esac
done

[ -n "$TO_IMAGE_TAG" ] || usage 2
if [[ ! "$TO_IMAGE_TAG" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$ ]]; then
    fail "--to is not a valid OCI image tag: $TO_IMAGE_TAG"
fi

for tool in docker curl jq python3 sha256sum tar; do
    command -v "$tool" > /dev/null || fail "$tool is required"
done
docker compose version > /dev/null || fail "the docker compose plugin is required"
for file in install.sh docker-compose.yml variables.env restore.sh; do
    [ -f "$SOURCE_DIR/$file" ] || fail "$SOURCE_DIR/$file not found"
done

if [ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")" ] \
    || docker volume ls -q | grep -q "^${PROJECT}_"; then
    fail "a $PROJECT deployment already exists on this Docker host; refusing to touch it"
fi

latest_stable_release() {
    if command -v gh > /dev/null && [ -n "${GH_TOKEN:-}" ]; then
        gh release view --repo "$GITHUB_REPOSITORY" --json tagName --jq .tagName
    else
        # /releases/latest never returns a draft or a prerelease.
        curl -fsSL "https://api.github.com/repos/$GITHUB_REPOSITORY/releases/latest" | jq -r .tag_name
    fi
}

if [ -z "$FROM_RELEASE" ]; then
    FROM_RELEASE=$(latest_stable_release)
fi
FROM_VERSION=${FROM_RELEASE#hangar-}
FROM_RELEASE=hangar-$FROM_VERSION
if [[ ! "$FROM_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    fail "--from must be a stable release such as hangar-v0.1.0, not '$FROM_RELEASE'"
fi

WORK_DIR=${WORK_DIR:-$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/compose-upgrade.XXXXXX")}
ARTIFACT_DIR=${ARTIFACT_DIR:-$WORK_DIR/artifacts}
mkdir -p "$WORK_DIR" "$ARTIFACT_DIR/logs"
WORK_DIR=$(cd "$WORK_DIR" && pwd)
ARTIFACT_DIR=$(cd "$ARTIFACT_DIR" && pwd)

# Seed credentials: random per run, kept out of the fingerprint and the logs.
SECRETS_DIR="$WORK_DIR/secrets"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"
random_value() { LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$1" || true; }
SEED_PASSWORD="Up-$(random_value 29)"
SEED_API_TOKEN="plane_api_$(random_value 32)"
export SEED_PASSWORD SEED_API_TOKEN
printf '%s' "$SEED_PASSWORD" > "$SECRETS_DIR/password"

echo "Upgrade from: $FROM_RELEASE (images $FROM_VERSION)"
echo "Upgrade to:   images $TO_IMAGE_TAG with $SOURCE_DIR"
echo "Work dir:     $WORK_DIR"
echo "Artifacts:    $ARTIFACT_DIR"

compose() {
    (cd "$CURRENT_DEPLOYMENT/$PROJECT" && docker compose -f docker-compose.yaml --env-file plane.env "$@")
}

env_value() {
    grep "^$1=" "$CURRENT_DEPLOYMENT/$PROJECT/plane.env" | tail -n 1 | cut -d= -f2- || true
}

collect_logs() {
    local name=$1
    [ -n "$CURRENT_DEPLOYMENT" ] && [ -f "$CURRENT_DEPLOYMENT/$PROJECT/docker-compose.yaml" ] || return 0
    compose ps -a > "$ARTIFACT_DIR/logs/$name-ps.txt" 2>&1 || true
    compose logs --no-color --timestamps > "$ARTIFACT_DIR/logs/$name-compose.log" 2>&1 || true
}

remove_deployment() {
    [ -n "$CURRENT_DEPLOYMENT" ] && [ -f "$CURRENT_DEPLOYMENT/$PROJECT/docker-compose.yaml" ] || return 0
    compose down -v --remove-orphans > /dev/null 2>&1 || true
}

on_exit() {
    local status=$?
    set +e
    if [ "$status" -ne 0 ]; then
        echo "Failed during: $PHASE" >&2
        collect_logs "failed-$PHASE"
    fi
    if [ "${KEEP_DEPLOYMENT:-0}" != "1" ] || [ "$status" -ne 0 ]; then
        remove_deployment
        # restore.sh recreates volumes outside Compose, so name them too.
        docker volume ls -q | grep "^${PROJECT}_" | xargs -r docker volume rm > /dev/null 2>&1
    fi
    rm -rf "$SECRETS_DIR"
    exit "$status"
}
trap on_exit EXIT

wait_healthy() {
    local deadline=$((SECONDS + HEALTH_TIMEOUT)) pending id name health state migrator
    while :; do
        pending=""
        for id in $(compose ps -q); do
            name=$(docker inspect --format '{{.Name}}' "$id")
            health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id")
            state=$(docker inspect --format '{{.State.Status}}' "$id")
            case "$health/$state" in
                healthy/running|none/running) ;;
                *) pending="$pending $name=$health/$state" ;;
            esac
        done
        migrator=$(compose ps -a -q migrator)
        if [ -n "$migrator" ] && [ "$(docker inspect --format '{{.State.Status}}' "$migrator")" = exited ] \
            && [ "$(docker inspect --format '{{.State.ExitCode}}' "$migrator")" != 0 ]; then
            fail "the migrator exited with an error"
        fi
        [ -z "$pending" ] && break
        if [ "$SECONDS" -ge "$deadline" ]; then
            compose ps -a
            fail "not healthy after ${HEALTH_TIMEOUT}s:$pending"
        fi
        sleep 10
    done
    compose ps
}

wait_http() {
    local path=$1 status=""
    for _ in $(seq 1 60); do
        status=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL$path" || true)
        [ "$status" = 200 ] && return 0
        sleep 5
    done
    fail "$path returned $status"
}

# Runs compose_seed.py in the api container and writes the fingerprint.
fingerprint() {
    local mode=$1 output=$2 raw
    raw=$(compose exec -T -e SEED_PASSWORD -e SEED_API_TOKEN api python - "--$mode" < "$SEED_SCRIPT")
    printf '%s\n' "$raw" | sed -n 's/^HANGAR_FINGERPRINT //p' | tail -n 1 | jq -S . > "$output"
    [ -s "$output" ] || { printf '%s\n' "$raw" >&2; fail "compose_seed.py --$mode printed no fingerprint"; }
}

check_fingerprint_contents() {
    jq -e '
        .instance_setup_done
        and (.users | length == 3 and all(.password_matches and .is_active))
        and (.workspaces | length == 2)
        and (.workspace_members | length == 5)
        and (.project.members | length == 3)
        and (.issues | length == 1) and (.comments | length == 1) and (.worklogs | length == 1)
        and (.attachments | length == 1 and all(.stored_sha256 == $expected and .is_uploaded))
        and .api_token.matches and .api_token.is_active
    ' --arg expected "$(jq -r .expected_attachment_sha256 "$1")" "$1" > /dev/null \
        || { cat "$1"; fail "$1 does not describe the seeded data"; }
}

compare_fingerprint() {
    local label=$1 actual=$2
    check_fingerprint_contents "$actual"
    if ! diff -u "$ARTIFACT_DIR/fingerprint-seed.json" "$actual"; then
        fail "the data differs from the seed after $label"
    fi
    echo "Fingerprint after $label matches the seed"
}

# Password sign-in through the proxy, then the session and an API-key call.
check_http() {
    local label=$1 jar headers csrf location project_id
    jar="$SECRETS_DIR/cookies-$label"
    headers="$SECRETS_DIR/headers-$label"
    wait_http /
    wait_http /api/instances/
    csrf=$(curl -fsS -c "$jar" -b "$jar" "$BASE_URL/auth/get-csrf-token/" | jq -r .csrf_token)
    [ -n "$csrf" ] && [ "$csrf" != null ] || fail "no CSRF token ($label)"
    curl -sS -o /dev/null -D "$headers" -c "$jar" -b "$jar" \
        -H "Origin: $BASE_URL" -H "Referer: $BASE_URL/" \
        --data-urlencode "csrfmiddlewaretoken=$csrf" \
        --data-urlencode "email=$ADMIN_EMAIL" \
        --data-urlencode "password@$SECRETS_DIR/password" \
        "$BASE_URL/auth/sign-in/"
    location=$(sed -n 's/^[Ll]ocation: *//p' "$headers" | tr -d '\r')
    case "$location" in
        *error_code*|"") fail "password sign-in failed ($label): redirected to '${location:-nowhere}'" ;;
    esac
    curl -fsS -b "$jar" "$BASE_URL/api/users/me/" \
        | jq -e --arg email "$ADMIN_EMAIL" '.email == $email' > /dev/null \
        || fail "the signed-in session is not the seeded admin ($label)"
    echo "Password sign-in works ($label)"

    project_id=$(curl -fsS -H "X-API-Key: $SEED_API_TOKEN" \
        "$BASE_URL/api/v1/workspaces/upgrade-alpha/projects/" \
        | jq -r '.results[] | select(.identifier == "UPG") | .id')
    [ -n "$project_id" ] || fail "the API key does not list the seeded project ($label)"
    curl -fsS -H "X-API-Key: $SEED_API_TOKEN" \
        "$BASE_URL/api/v1/workspaces/upgrade-alpha/projects/$project_id/issues/" \
        | jq -e '[.results[].name] == ["Upgrade survives with its data"]' > /dev/null \
        || fail "the API key does not list the seeded work item ($label)"
    echo "API-key access works ($label)"
}

is_template_secret() {
    local value=$1
    [ -z "$value" ] || [[ "$TEMPLATE_SECRET_KEYS" == *" $value "* ]]
}

# --- 1. Install the previous release with its own installer and assets ------
PHASE=install-from
log "Installing $FROM_RELEASE with its own setup.sh"
FROM_DIR="$WORK_DIR/from"
mkdir -p "$FROM_DIR/$PROJECT" "$WORK_DIR/from-assets"
for asset in setup.sh docker-compose.yml variables.env; do
    curl -fsSL -o "$WORK_DIR/from-assets/$asset" \
        "https://github.com/$GITHUB_REPOSITORY/releases/download/$FROM_RELEASE/$asset"
done
cp "$WORK_DIR/from-assets/setup.sh" "$FROM_DIR/setup.sh"
# An existing plane.env pins the release, which keeps the installer off the
# GitHub API and its interactive release check; the installer merges these
# values into the template it downloads. Secrets keep their template values,
# as an operator following that release's README had them.
cat > "$FROM_DIR/$PROJECT/plane.env" <<EOF
APP_RELEASE=$FROM_VERSION
APP_DOMAIN=localhost:$HTTP_PORT
LISTEN_HTTP_PORT=$HTTP_PORT
LISTEN_HTTPS_PORT=$HTTPS_PORT
EOF
CURRENT_DEPLOYMENT=$FROM_DIR
(cd "$FROM_DIR" && bash ./setup.sh install < /dev/null)
[ "$(env_value APP_RELEASE)" = "$FROM_VERSION" ] || fail "setup.sh did not pin APP_RELEASE=$FROM_VERSION"
# The installer writes the download through echo, which may change trailing newlines.
diff -B -q "$WORK_DIR/from-assets/docker-compose.yml" "$FROM_DIR/$PROJECT/docker-compose.yaml" > /dev/null \
    || fail "setup.sh installed a docker-compose.yml other than the $FROM_RELEASE asset"
FROM_SECRET_KEY=$(env_value SECRET_KEY)

PHASE=start-from
log "Starting $FROM_RELEASE"
(cd "$FROM_DIR" && bash ./setup.sh start < /dev/null)
wait_healthy

PHASE=seed
log "Seeding"
fingerprint seed "$ARTIFACT_DIR/fingerprint-seed.json"
check_fingerprint_contents "$ARTIFACT_DIR/fingerprint-seed.json"
cat "$ARTIFACT_DIR/fingerprint-seed.json"
check_http "$FROM_VERSION"

# --- 2. Back up with the installer -------------------------------------------
PHASE=backup
log "Backing up with setup.sh backup"
# Flush to disk: the backup copies the data directories of running services.
# Over the local socket, which needs no password; the container's PGHOST
# would send psql over TCP.
# shellcheck disable=SC2016 # expanded inside the container
compose exec -T plane-db sh -c 'psql -h /var/run/postgresql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c CHECKPOINT' > /dev/null
(cd "$FROM_DIR" && bash "$SOURCE_DIR/install.sh" --yes backup < /dev/null)
backup_source=$(find "$FROM_DIR/$PROJECT/backup" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)
[ -n "$backup_source" ] || fail "setup.sh backup left no backup folder"
BACKUP_DIR="$ARTIFACT_DIR/backup"
mkdir -p "$BACKUP_DIR"
cp "$backup_source"/*.tar.gz "$BACKUP_DIR/"
# The volumes hold data written with these passwords and keys; a restore needs both.
cp "$FROM_DIR/$PROJECT/plane.env" "$BACKUP_DIR/plane.env"
chmod 600 "$BACKUP_DIR/plane.env"
for archive in pgdata object-storage rabbitmq_data redisdata; do
    [ -s "$BACKUP_DIR/$archive.tar.gz" ] || fail "the backup has no $archive.tar.gz"
done
(cd "$BACKUP_DIR" && sha256sum ./*.tar.gz > SHA256SUMS && cat SHA256SUMS)

# --- 3. Upgrade with the candidate's installer -------------------------------
PHASE=upgrade
log "Upgrading to $TO_IMAGE_TAG with the candidate installer"
export HANGAR_ASSUME_YES=1 HANGAR_INSTALL_SOURCE_DIR="$SOURCE_DIR" HANGAR_RELEASE="$TO_IMAGE_TAG"
if [ "$TO_IMAGE_TAG" = "$FROM_VERSION" ]; then
    # upgrade stops at "already using the latest release" for the same tag;
    # stop + install runs the same download, merge and secret replacement.
    echo "Same image tag: running stop + install, the steps upgrade runs"
    (cd "$FROM_DIR" && bash "$SOURCE_DIR/install.sh" --yes stop < /dev/null)
    (cd "$FROM_DIR" && bash "$SOURCE_DIR/install.sh" --yes install < /dev/null)
else
    (cd "$FROM_DIR" && bash "$SOURCE_DIR/install.sh" --yes upgrade < /dev/null)
fi
[ "$(env_value APP_RELEASE)" = "$TO_IMAGE_TAG" ] || fail "the upgrade did not set APP_RELEASE=$TO_IMAGE_TAG"
cmp -s "$SOURCE_DIR/docker-compose.yml" "$FROM_DIR/$PROJECT/docker-compose.yaml" \
    || fail "the upgrade did not install the candidate docker-compose.yml"
for name in SECRET_KEY LIVE_SERVER_SECRET_KEY; do
    value=$(env_value "$name")
    if is_template_secret "$value" || [ "$value" = secret-key ] || [ "$value" = htbqvBJAgpm9bzvf3r4urJer0ENReatceh ]; then
        fail "$name is still empty or a template value after the upgrade"
    fi
done
if ! is_template_secret "$FROM_SECRET_KEY" && [ "$(env_value SECRET_KEY)" != "$FROM_SECRET_KEY" ]; then
    fail "the upgrade replaced a SECRET_KEY that was not a template value"
fi
[ "$(env_value POSTGRES_PASSWORD)" = "$(grep '^POSTGRES_PASSWORD=' "$BACKUP_DIR/plane.env" | cut -d= -f2-)" ] \
    || fail "the upgrade changed POSTGRES_PASSWORD of an existing database"

PHASE=start-upgraded
(cd "$FROM_DIR" && bash "$SOURCE_DIR/install.sh" --yes start < /dev/null)
wait_healthy

PHASE=verify-upgraded
log "Verifying the upgraded deployment"
fingerprint verify "$ARTIFACT_DIR/fingerprint-upgraded.json"
compare_fingerprint upgrade "$ARTIFACT_DIR/fingerprint-upgraded.json"
check_http upgraded
collect_logs upgraded

# --- 4. Restore the backup into a fresh install ------------------------------
PHASE=remove-upgraded
log "Removing the upgraded deployment and its volumes"
remove_deployment
if docker volume ls -q | grep -q "^${PROJECT}_"; then
    fail "volumes of the removed deployment remain"
fi

PHASE=restore
log "Restoring the backup into a fresh directory"
RESTORE_DIR="$WORK_DIR/restore"
mkdir -p "$RESTORE_DIR/$PROJECT"
CURRENT_DEPLOYMENT=$RESTORE_DIR
cp "$BACKUP_DIR/plane.env" "$RESTORE_DIR/$PROJECT/plane.env"
cp "$SOURCE_DIR/restore.sh" "$RESTORE_DIR/restore.sh"
# restore.sh fills existing volumes only. They are restored before the
# installer runs, so it sees an existing database and keeps its password.
for volume in pgdata redisdata object-storage rabbitmq_data; do
    docker volume create "${PROJECT}_${volume}" > /dev/null
done
(cd "$RESTORE_DIR" && TERM=${TERM:-dumb} bash ./restore.sh "$BACKUP_DIR" < /dev/null)
(cd "$RESTORE_DIR" && bash "$SOURCE_DIR/install.sh" --yes install < /dev/null)
[ "$(env_value POSTGRES_PASSWORD)" = "$(grep '^POSTGRES_PASSWORD=' "$BACKUP_DIR/plane.env" | cut -d= -f2-)" ] \
    || fail "the install changed POSTGRES_PASSWORD of the restored database"

PHASE=start-restored
(cd "$RESTORE_DIR" && bash "$SOURCE_DIR/install.sh" --yes start < /dev/null)
wait_healthy

PHASE=verify-restored
log "Verifying the restored deployment"
fingerprint verify "$ARTIFACT_DIR/fingerprint-restored.json"
compare_fingerprint restore "$ARTIFACT_DIR/fingerprint-restored.json"
check_http restored
collect_logs restored

PHASE=finished
log "Upgrade from $FROM_RELEASE to $TO_IMAGE_TAG and restore of its backup passed"
