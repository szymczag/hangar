#!/usr/bin/env bash
#
# Copy a Hangar install's uploads from the legacy MinIO volume into the
# SeaweedFS volume that the bundled object storage now uses.
#
# MinIO's community images are no longer published, and SeaweedFS cannot read
# MinIO's on-disk format, so the data is copied object by object over the S3
# API: a temporary MinIO-compatible server reads the old volume, a temporary
# SeaweedFS writes the new one, and rclone copies and then verifies every
# bucket. The legacy volume is never deleted or rewritten, so rolling back is
# a matter of pointing the old compose file at it again.
#
# Run it with the stack stopped. `setup.sh upgrade` calls it automatically when
# it finds a legacy volume and no SeaweedFS volume yet.

set -euo pipefail

# Pinned by multi-arch index digest. LEGACY_IMAGE / SEAWEEDFS_IMAGE /
# RCLONE_IMAGE override them (e.g. for an air-gapped mirror).
MINIO_CACHED_IMAGE="quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
# A maintained MinIO fork that reads the same on-disk format. Used only to read
# the old volume when the original MinIO image is no longer cached locally.
MINIO_FALLBACK_IMAGE="docker.io/pgsty/silo:RELEASE.2026-09-16T00-00-00Z@sha256:635197cb9f36d01bee221d34d1c7d7960f6a95c48b0b6c01d99cd13bdae51a46"
DEFAULT_SEAWEEDFS_IMAGE="docker.io/chrislusf/seaweedfs:4.48@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d"
DEFAULT_RCLONE_IMAGE="docker.io/rclone/rclone:1.75.2@sha256:2687085f718d3c628f7fdfb77c52a1d344332aed543110bb88088f2c70d43eb5"

CLI="${CONTAINER_CLI:-docker}"
PROJECT="plane-app"
ENV_FILE=""
LEGACY_VOLUME=""
TARGET_VOLUME=""
ASSUME_YES=0
CHECK_ONLY=0
# Written into the target volume only after every bucket has been verified.
MARKER=".hangar-migrated-from-minio"

usage() {
    cat <<EOF
Usage: $0 [options]

  --project NAME         Compose project name (default: plane-app)
  --env-file FILE        plane.env holding AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
                         (and LEGACY_MINIO_ROOT_USER / _PASSWORD for the old volume)
  --legacy-volume NAME   MinIO volume to read (default: <project>_uploads)
  --target-volume NAME   SeaweedFS volume to fill (default: <project>_object-storage)
  --yes                  Do not ask for confirmation
  --check                Only report: exit 0 when no migration is pending, 3 when one is
  -h, --help             Show this help

Environment: CONTAINER_CLI (docker|podman), LEGACY_IMAGE, SEAWEEDFS_IMAGE, RCLONE_IMAGE.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --project) PROJECT="$2"; shift 2 ;;
        --env-file) ENV_FILE="$2"; shift 2 ;;
        --legacy-volume) LEGACY_VOLUME="$2"; shift 2 ;;
        --target-volume) TARGET_VOLUME="$2"; shift 2 ;;
        --yes|-y) ASSUME_YES=1; shift ;;
        --check) CHECK_ONLY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

LEGACY_VOLUME="${LEGACY_VOLUME:-${PROJECT}_uploads}"
TARGET_VOLUME="${TARGET_VOLUME:-${PROJECT}_object-storage}"

env_value() {
    # Read KEY from the env file without sourcing it; strips optional quotes.
    local key="$1" file="$2"
    [ -n "$file" ] && [ -f "$file" ] || return 0
    sed -n -E "s/^${key}=[\"']?([^\"']*)[\"']?[[:space:]]*$/\1/p" "$file" | tail -n 1
}

ACCESS_KEY="$(env_value AWS_ACCESS_KEY_ID "$ENV_FILE")"
SECRET_KEY="$(env_value AWS_SECRET_ACCESS_KEY "$ENV_FILE")"
ACCESS_KEY="${ACCESS_KEY:-${AWS_ACCESS_KEY_ID:-access-key}}"
SECRET_KEY="${SECRET_KEY:-${AWS_SECRET_ACCESS_KEY:-secret-key}}"
# setup.sh replaces the template pair and records the old one here; the legacy
# MinIO volume was written under it. Without a record the pair has not changed.
LEGACY_ACCESS_KEY="$(env_value LEGACY_MINIO_ROOT_USER "$ENV_FILE")"
LEGACY_SECRET_KEY="$(env_value LEGACY_MINIO_ROOT_PASSWORD "$ENV_FILE")"
LEGACY_ACCESS_KEY="${LEGACY_ACCESS_KEY:-$ACCESS_KEY}"
LEGACY_SECRET_KEY="${LEGACY_SECRET_KEY:-$SECRET_KEY}"

log() { printf '>> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

command -v "$CLI" >/dev/null 2>&1 || die "'$CLI' not found; set CONTAINER_CLI=podman if you use Podman."

volume_exists() { "$CLI" volume inspect "$1" >/dev/null 2>&1; }

volume_in_use() {
    [ -n "$("$CLI" ps -q --filter "volume=$1")" ]
}

has_marker() {
    volume_exists "$1" || return 1
    "$CLI" run --rm -v "$1:/v:ro" --entrypoint sh "$SEAWEEDFS_IMAGE" -c "test -f /v/$MARKER"
}

SEAWEEDFS_IMAGE="${SEAWEEDFS_IMAGE:-$DEFAULT_SEAWEEDFS_IMAGE}"
RCLONE_IMAGE="${RCLONE_IMAGE:-$DEFAULT_RCLONE_IMAGE}"
if [ -z "${LEGACY_IMAGE:-}" ]; then
    if "$CLI" image inspect "$MINIO_CACHED_IMAGE" >/dev/null 2>&1; then
        LEGACY_IMAGE="$MINIO_CACHED_IMAGE"
    else
        LEGACY_IMAGE="$MINIO_FALLBACK_IMAGE"
    fi
fi

if ! volume_exists "$LEGACY_VOLUME"; then
    [ "$CHECK_ONLY" -eq 1 ] && exit 0
    log "No legacy volume '$LEGACY_VOLUME'; nothing to migrate."
    exit 0
fi
if has_marker "$TARGET_VOLUME"; then
    [ "$CHECK_ONLY" -eq 1 ] && exit 0
    log "'$TARGET_VOLUME' is already migrated from '$LEGACY_VOLUME'. Nothing to do."
    exit 0
fi
[ "$CHECK_ONLY" -eq 1 ] && exit 3

if volume_in_use "$LEGACY_VOLUME"; then
    die "volume '$LEGACY_VOLUME' is in use by a running container. Stop the stack first (setup.sh stop)."
fi
if volume_exists "$TARGET_VOLUME" && volume_in_use "$TARGET_VOLUME"; then
    die "volume '$TARGET_VOLUME' is in use by a running container. Stop the stack first (setup.sh stop)."
fi

echo
echo "Object storage migration"
echo "  from (MinIO):     $LEGACY_VOLUME   read with $LEGACY_IMAGE"
echo "  to   (SeaweedFS): $TARGET_VOLUME"
echo "The legacy volume is kept unchanged for rollback."
echo
if [ "$ASSUME_YES" -ne 1 ]; then
    read -r -p "Continue? [y/N]: " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

RUN_ID="$(date +%s)-$$"
NETWORK="${PROJECT}-storage-migration-${RUN_ID}"
SRC="${PROJECT}-migrate-src-${RUN_ID}"
DST="${PROJECT}-migrate-dst-${RUN_ID}"
SUCCESS=0

cleanup() {
    "$CLI" rm -f "$SRC" "$DST" >/dev/null 2>&1 || true
    "$CLI" network rm "$NETWORK" >/dev/null 2>&1 || true
    if [ "$SUCCESS" -ne 1 ]; then
        echo
        echo "Migration did not complete. '$LEGACY_VOLUME' is untouched."
        echo "'$TARGET_VOLUME' was left for inspection; remove it before retrying:"
        echo "  $CLI volume rm $TARGET_VOLUME"
    fi
}
trap cleanup EXIT

log "Pulling images (if not present)"
for image in "$LEGACY_IMAGE" "$SEAWEEDFS_IMAGE" "$RCLONE_IMAGE"; do
    "$CLI" image inspect "$image" >/dev/null 2>&1 || "$CLI" pull -q "$image" >/dev/null
done

"$CLI" network create "$NETWORK" >/dev/null
volume_exists "$TARGET_VOLUME" || "$CLI" volume create "$TARGET_VOLUME" >/dev/null

log "Starting the legacy reader"
"$CLI" run -d --name "$SRC" --network "$NETWORK" \
    -e MINIO_ROOT_USER="$LEGACY_ACCESS_KEY" -e MINIO_ROOT_PASSWORD="$LEGACY_SECRET_KEY" \
    -v "$LEGACY_VOLUME:/export" \
    "$LEGACY_IMAGE" server /export >/dev/null

log "Starting SeaweedFS"
# Same hardening as the compose service: per-start JWT keys close the filer and
# volume HTTP ports, leaving only the authenticated S3 API.
"$CLI" run -d --name "$DST" --network "$NETWORK" --user 1000:1000 \
    -e AWS_ACCESS_KEY_ID="$ACCESS_KEY" -e AWS_SECRET_ACCESS_KEY="$SECRET_KEY" \
    -v "$TARGET_VOLUME:/data" \
    --entrypoint /bin/sh "$SEAWEEDFS_IMAGE" -c '
        for key in WEED_JWT_SIGNING_KEY WEED_JWT_SIGNING_READ_KEY WEED_JWT_FILER_SIGNING_KEY WEED_JWT_FILER_SIGNING_READ_KEY; do
          export "$key=$(head -c 32 /dev/urandom | base64 | tr -d "=+/\n")"
        done
        exec weed -logtostderr=true mini -dir=/data -ip='"$DST"' -ip.bind=0.0.0.0 -s3.port=9000 \
          -master.telemetry=false -admin.ui=false -webdav=false' >/dev/null

rclone() {
    "$CLI" run --rm --network "$NETWORK" -e RCLONE_CONFIG=/dev/null \
        -e RCLONE_CONFIG_SRC_TYPE=s3 -e RCLONE_CONFIG_SRC_PROVIDER=Minio \
        -e RCLONE_CONFIG_SRC_ENDPOINT="http://$SRC:9000" \
        -e RCLONE_CONFIG_SRC_ACCESS_KEY_ID="$LEGACY_ACCESS_KEY" -e RCLONE_CONFIG_SRC_SECRET_ACCESS_KEY="$LEGACY_SECRET_KEY" \
        -e RCLONE_CONFIG_DST_TYPE=s3 -e RCLONE_CONFIG_DST_PROVIDER=SeaweedFS \
        -e RCLONE_CONFIG_DST_ENDPOINT="http://$DST:9000" \
        -e RCLONE_CONFIG_DST_ACCESS_KEY_ID="$ACCESS_KEY" -e RCLONE_CONFIG_DST_SECRET_ACCESS_KEY="$SECRET_KEY" \
        "$RCLONE_IMAGE" "$@"
}

wait_for() {
    local remote="$1" i
    for i in $(seq 1 60); do
        rclone lsf --dirs-only "$remote" >/dev/null 2>&1 && return 0
        sleep 2
    done
    "$CLI" logs --tail 20 "${2}" >&2 || true
    die "the ${remote%:} server did not become ready"
}
wait_for src: "$SRC"
wait_for dst: "$DST"

BUCKETS="$(rclone lsf --dirs-only src: | sed 's#/$##')"
if [ -z "$BUCKETS" ]; then
    log "The legacy storage holds no buckets."
fi

for bucket in $BUCKETS; do
    log "Copying bucket '$bucket'"
    rclone mkdir "dst:$bucket"
    rclone copy "src:$bucket" "dst:$bucket" --transfers 8 --checkers 16 --stats-one-line --stats 30s
    log "Verifying bucket '$bucket'"
    # Compare content, not just size: multipart uploads carry no MD5 ETag, so a
    # hash-only check would wave those objects through on size alone.
    rclone check "src:$bucket" "dst:$bucket" --one-way --download --checkers 8
    count="$(rclone lsf -R --files-only "src:$bucket" | wc -l | tr -d ' ')"
    log "Bucket '$bucket': $count object(s) copied and verified"
done

# The copy is additive (rclone copy never deletes), so objects written to the
# new storage before the migration ran are kept alongside the copied ones.
"$CLI" rm -f "$DST" >/dev/null
"$CLI" run --rm --user 1000:1000 -v "$TARGET_VOLUME:/v" --entrypoint sh "$SEAWEEDFS_IMAGE" \
    -c "date -u +%Y-%m-%dT%H:%M:%SZ > /v/$MARKER"

SUCCESS=1
echo
log "Migration finished. Start the stack with the new compose file (setup.sh start)."
log "Once uploads are confirmed working, the legacy volume can be removed with:"
echo "     $CLI volume rm $LEGACY_VOLUME"
