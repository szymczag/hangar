#!/usr/bin/env bash

# BRANCH set by the operator is the only way deployment files may come from a
# branch rather than a release, when the release cannot be downloaded. Without
# it, a failed release download is an error.
BRANCH_REQUESTED=${BRANCH:-}
BRANCH=${BRANCH:-preview}
SERVICE_FOLDER=plane-app
SCRIPT_DIR=$PWD
PLANE_INSTALL_DIR=$PWD/$SERVICE_FOLDER
export APP_RELEASE="stable"
export DOCKERHUB_USER=ghcr.io/szymczag

export GH_REPO=szymczag/hangar
export RELEASE_DOWNLOAD_URL="https://github.com/$GH_REPO/releases/download"
export FALLBACK_DOWNLOAD_URL="https://raw.githubusercontent.com/$GH_REPO/$BRANCH/deployments/cli/community"

OS_NAME=$(uname)

# Create necessary directories
mkdir -p "$PLANE_INSTALL_DIR"
# Holds earlier copies of plane.env: owner only, like plane.env itself.
( umask 077 && mkdir -p "$PLANE_INSTALL_DIR/archive" )

DOCKER_FILE_PATH=$PLANE_INSTALL_DIR/docker-compose.yml
STACK_FILE_PATH=$PLANE_INSTALL_DIR/docker-stack.yml
DOCKER_ENV_PATH=$PLANE_INSTALL_DIR/plane.env

# Unattended use: HANGAR_ASSUME_YES=1 (or --yes) answers the upgrade prompt
# with yes and does not clear the screen.
# HANGAR_REQUIRE_SIGNATURE=1 refuses deployment files whose Cosign signature
# cannot be checked: no cosign, a release without SHA256SUMS, or a branch.
# HANGAR_RELEASE=vX.Y.Z deploys or upgrades to that release instead of asking
# the GitHub API for the latest one, which rate-limits anonymous use.
HANGAR_ASSUME_YES=${HANGAR_ASSUME_YES:-0}
HANGAR_RELEASE=${HANGAR_RELEASE:-}
HANGAR_REQUIRE_SIGNATURE=${HANGAR_REQUIRE_SIGNATURE:-0}

function print_header() {
if [ "$HANGAR_ASSUME_YES" != "1" ] && [ -t 1 ]; then
    clear
fi

cat <<"EOF"
--------------------------------------------
 ____  _                          ///////// 
|  _ \| | __ _ _ __   ___         ///////// 
| |_) | |/ _` | '_ \ / _ \   /////    ///// 
|  __/| | (_| | | | |  __/   /////    ///// 
|_|   |_|\__,_|_| |_|\___|        ////      
                                  ////      
--------------------------------------------
Project management tool from the future
--------------------------------------------
EOF
}

function checkLatestRelease(){
    echo "Checking for the latest release..." >&2
    # Take the newest stable release, or the newest pre-release while no
    # stable release exists. The list is newest first, anonymous requests never
    # see drafts, and in each release "tag_name" precedes "prerelease".
    # /releases/latest is not used: it never returns a pre-release, so it finds
    # nothing until the first stable release. Release tags are hangar-vX.Y.Z;
    # images are tagged vX.Y.Z.
    local latest_release=$(curl -sSL "https://api.github.com/repos/$GH_REPO/releases?per_page=100" \
        | grep -o '"tag_name": *"[^"]*"\|"prerelease": *[a-z]*' \
        | awk -F'"' '
            /"tag_name"/ { tag = ($4 ~ /^hangar-v/) ? $4 : ""; next }
            tag != "" {
                if (newest == "") newest = tag
                if ($0 ~ /false$/ && stable == "") stable = tag
                tag = ""
            }
            END { print (stable != "" ? stable : newest) }' \
        | sed 's/^hangar-//')
    if [ -z "$latest_release" ]; then
        echo "Failed to check for the latest release. Exiting..." >&2
        exit 1
    fi

    echo $latest_release
}

# Function to read stack name from env file
function readStackName() {
    if [ -f "$DOCKER_ENV_PATH" ]; then
        local saved_stack_name=$(grep "^STACK_NAME=" "$DOCKER_ENV_PATH" | cut -d'=' -f2)
        if [ -n "$saved_stack_name" ]; then
            stack_name=$saved_stack_name
            return 1
        fi
    fi
    return 0
}

# Function to get stack name (either from env or user input)
function getStackName() {
    read -p "Enter stack name [plane]: " input_stack_name
    if [ -z "$input_stack_name" ]; then
        input_stack_name="plane"
    fi
    stack_name=$input_stack_name
    updateEnvFile "STACK_NAME" "$stack_name" "$DOCKER_ENV_PATH"
    echo "Using stack name: $stack_name"
}

function syncEnvFile(){
    echo "Syncing environment variables..." >&2
    if [ -f "$PLANE_INSTALL_DIR/plane.env.bak" ]; then        
        # READ keys of plane.env and update the values from plane.env.bak
        while IFS= read -r line
        do
            # ignore if the line is empty or starts with #
            if [ -z "$line" ] || [[ $line == \#* ]]; then
                continue
            fi
            key=$(echo "$line" | cut -d'=' -f1)
            value=$(getEnvValue "$key" "$PLANE_INSTALL_DIR/plane.env.bak")
            if [ -n "$value" ]; then
                updateEnvFile "$key" "$value" "$DOCKER_ENV_PATH"
            fi
        done < "$DOCKER_ENV_PATH"

        value=$(getEnvValue "STACK_NAME" "$PLANE_INSTALL_DIR/plane.env.bak")
        if [ -n "$value" ]; then
            updateEnvFile "STACK_NAME" "$value" "$DOCKER_ENV_PATH"
        fi
    fi
    echo "Environment variables synced successfully" >&2
    rm -f $PLANE_INSTALL_DIR/plane.env.bak
}

# plane.env holds SECRET_KEY and the database, broker, cache and object-storage
# credentials. It, every copy kept of it (plane.env.bak and
# archive/<timestamp>.env) and the directories holding those copies are
# readable by the owner only, whatever the umask. The same in install.sh and
# swarm.sh. Env files are copied and moved only through copyEnvFile and
# moveEnvFile; a bare cp or mv would give the copy the umask's mode instead.

# Copies env file $1 to $2 with mode 600, also when $2 already exists.
function copyEnvFile() {
    local src=$1 dest=$2
    rm -f "$dest" || return 1
    ( umask 077 && cp "$src" "$dest" ) && chmod 600 "$dest"
}

# Moves env file $1 to $2 with mode 600. The mode is set first, so the file
# never sits at $2 readable by others.
function moveEnvFile() {
    chmod 600 "$1" && mv "$1" "$2"
}

# Prints the permission bits of $1 in octal: GNU stat, or BSD stat on macOS.
function fileMode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null
}

# Removes group and other access from each existing path given that has any,
# and says so in one line.
function restrictToOwner() {
    local path mode tightened=()
    for path in "$@"; do
        [ -e "$path" ] || continue
        mode=$(fileMode "$path")
        [ -n "$mode" ] || continue
        if [ $((8#$mode & 8#077)) -ne 0 ] && chmod go-rwx "$path"; then
            tightened+=("${path#"$PLANE_INSTALL_DIR"/}")
        fi
    done
    if [ ${#tightened[@]} -gt 0 ]; then
        echo "NOTICE: restricted to the owner, because other local users could read them: ${tightened[*]}" >&2
    fi
}

# Releases before this check kept plane.env, plane.env.bak and archive/*.env
# at the umask's mode, often 664 or 644. Tightens what an earlier release left.
function protectEnvFiles() {
    local archived=()
    if [ -d "$PLANE_INSTALL_DIR/archive" ]; then
        archived=("$PLANE_INSTALL_DIR"/archive/*.env)
    fi
    restrictToOwner "$PLANE_INSTALL_DIR/archive" "$PLANE_INSTALL_DIR/backup" "$DOCKER_ENV_PATH" \
        "$PLANE_INSTALL_DIR/plane.env.bak" "${archived[@]}"
}

function getEnvValue() {
    local key=$1
    local file=$2

    if [ -z "$key" ] || [ -z "$file" ]; then
        echo "Invalid arguments supplied"
        exit 1
    fi

    if [ -f "$file" ]; then
        grep -q "^$key=" "$file"
        if [ $? -eq 0 ]; then
            local value
            # -f2-: a value may itself contain '=' (URLs with a query string).
            value=$(grep "^$key=" "$file" | cut -d'=' -f2-)
            echo "$value"
        else
            echo ""
        fi
    fi
}

function updateEnvFile() {
    local key=$1
    local value=$2
    local file=$3

    if [ -z "$key" ] || [ -z "$value" ] || [ -z "$file" ]; then
        echo "Invalid arguments supplied"
        exit 1
    fi

    if [ -f "$file" ]; then
        # check if key exists in the file
        grep -q "^$key=" "$file"
        if [ $? -ne 0 ]; then
            echo "$key=$value" >> "$file"
            return
        else 
            # Escape what sed treats specially in a replacement: the
            # delimiter, '&' and the backslash.
            if [ "$OS_NAME" == "Darwin" ]; then
                value=$(printf '%s\n' "$value" | sed -e 's/[|&\\]/\\&/g')
                sed -i '' "s|^$key=.*|$key=$value|g" "$file"
            else
                value=$(printf '%s\n' "$value" | sed -e 's/[\/&\\]/\\&/g')
                sed -i "s/^$key=.*/$key=$value/g" "$file"
            fi
        fi
    else
        echo "File not found: $file"
        exit 1
    fi
}

# The bundled object storage takes its login from plane.env, and the proxy serves
# its S3 API on the application's origin: with the template pair anybody can sign
# requests that list, read, overwrite or delete every upload. Replace that pair on
# install and on upgrade; external S3 settings are left alone.
function generateStorageCredentials(){
    local use_minio endpoint access_key secret_key
    use_minio=$(getEnvValue "USE_MINIO" "$DOCKER_ENV_PATH")
    endpoint=$(getEnvValue "AWS_S3_ENDPOINT_URL" "$DOCKER_ENV_PATH")
    use_minio=${use_minio//[\"\']/}
    endpoint=${endpoint//[\"\']/}
    if [ "${use_minio:-1}" != "1" ] || [ "${endpoint:-http://plane-minio:9000}" != "http://plane-minio:9000" ]; then
        return 0
    fi

    # Empty values fall back to the template pair in docker-compose.yml. Older
    # templates quoted the values, so quotes are ignored when comparing.
    access_key=$(getEnvValue "AWS_ACCESS_KEY_ID" "$DOCKER_ENV_PATH")
    secret_key=$(getEnvValue "AWS_SECRET_ACCESS_KEY" "$DOCKER_ENV_PATH")
    access_key=${access_key//[\"\']/}
    secret_key=${secret_key//[\"\']/}
    # The secret is what protects the store, so a pair with any other secret stays.
    if [ "${secret_key:-secret-key}" != "secret-key" ]; then
        return 0
    fi

    # A legacy MinIO volume was written under the old login; migrate-object-storage.sh
    # reads it with these. They are the public template values, not a secret.
    if [ -z "$(getEnvValue "LEGACY_MINIO_ROOT_PASSWORD" "$DOCKER_ENV_PATH")" ]; then
        updateEnvFile "LEGACY_MINIO_ROOT_USER" "${access_key:-access-key}" "$DOCKER_ENV_PATH"
        updateEnvFile "LEGACY_MINIO_ROOT_PASSWORD" "secret-key" "$DOCKER_ENV_PATH"
    fi

    local new_access new_secret
    new_access=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 20)
    new_secret=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 40)
    if [ ${#new_access} -ne 20 ] || [ ${#new_secret} -ne 40 ]; then
        echo "Failed to generate object-storage credentials. Exiting..." >&2
        exit 1
    fi
    updateEnvFile "AWS_ACCESS_KEY_ID" "$new_access" "$DOCKER_ENV_PATH"
    updateEnvFile "AWS_SECRET_ACCESS_KEY" "$new_secret" "$DOCKER_ENV_PATH"
    if [ -n "$access_key$secret_key" ]; then
        echo "NOTICE: the template object-storage credentials were replaced; the new AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are in plane.env. Update any external client that used the old pair." >&2
    else
        echo "Generated object-storage credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) in plane.env" >&2
    fi
}

function randomSecret() {
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$1"
}

function isListed() {
    local value=$1 item
    shift
    for item in "$@"; do
        if [ "$value" == "$item" ]; then
            return 0
        fi
    done
    return 1
}

# The volumes on this host. A function of its own so tests can replace it.
function listVolumes() {
    docker volume ls -q 2>/dev/null
}

# Returns 0 when this deployment's volume with the given suffix exists, 1 when
# it does not, and 2 when Docker could not be asked.
function dataVolumeExists() {
    local suffix=$1 project volumes
    project=${COMPOSE_PROJECT_NAME:-$(getEnvValue "COMPOSE_PROJECT_NAME" "$DOCKER_ENV_PATH")}
    project=${project:-$DEPLOYMENT_NAME}
    volumes=$(listVolumes) || return 2
    if printf '%s\n' "$volumes" | grep -qxF "${project}_${suffix}"; then
        return 0
    fi
    return 1
}

# Older docker-compose.yml files connected the API with a fixed plane:plane URL
# and ignored POSTGRES_* and RABBITMQ_*; the API now connects with those. A
# deployment that changed them after its database or broker was created kept
# working only because they were ignored, so it keeps the old URL in plane.env.
function keepLegacyConnection() {
    local url_name=$1 legacy_url=$2 expected=$3 actual=$4
    if [ -z "$PREVIOUS_COMPOSE_PATH" ] || [ ! -f "$PREVIOUS_COMPOSE_PATH" ]; then
        return 0
    fi
    if ! grep -qF "\${$url_name:-$legacy_url}" "$PREVIOUS_COMPOSE_PATH"; then
        return 0
    fi
    if [ -n "$(getEnvValue "$url_name" "$DOCKER_ENV_PATH")" ] || [ "$actual" == "$expected" ]; then
        return 0
    fi
    updateEnvFile "$url_name" "$legacy_url" "$DOCKER_ENV_PATH"
    echo "WARNING: $url_name was set to $legacy_url in plane.env, the connection the previous release used whatever plane.env said. Rotate the password with the README procedure (Upgrading), then empty $url_name." >&2
}

function envSetting() {
    local value
    value=$(getEnvValue "$1" "$DOCKER_ENV_PATH")
    value=${value//[\"\']/}
    echo "${value:-$2}"
}

# The database and broker keep the password they were created with in their
# volumes, so a password is generated only for a deployment that has no volume
# yet. An existing deployment on the published default keeps it, with a warning.
function generateServicePassword() {
    local name=$1 url_name=$2 suffix=$3 current replacement
    current=$(envSetting "$name" "")
    # An explicit URL carries its own password; the two have to keep matching.
    if [ -n "$(getEnvValue "$url_name" "$DOCKER_ENV_PATH")" ]; then
        return 0
    fi
    if [ -n "$current" ] && [ "$current" != "plane" ]; then
        return 0
    fi
    if isNewDeployment "$suffix"; then
        replacement=$(randomSecret 32)
        if [ ${#replacement} -ne 32 ]; then
            echo "Failed to generate $name. Exiting..." >&2
            exit 1
        fi
        updateEnvFile "$name" "$replacement" "$DOCKER_ENV_PATH"
        echo "Generated $name in plane.env" >&2
    else
        echo "WARNING: $name is the published default 'plane'. It is kept because the existing ${suffix} volume was created with it; changing plane.env alone would lock the API out. Rotate it with the procedure in the README (Upgrading)." >&2
    fi
}

# SECRET_KEY is also the HMAC key behind identifiers Google Calendar capacity
# keeps: the hashes of each trainer's selected calendars and the keys that tie
# trainings imported from Google to their occurrences and sessions. The keys
# cannot be recomputed without Google's data, so replacing a template key on a
# deployment that uses the feature is refused unless the operator says so.
# Runs on the plane.env in place, before anything is downloaded or stopped.
function checkSecretKeyRotation() {
    local insecure_secret_keys="60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5 change-this-key-on-deployment"
    local current calendar
    if [ ! -f "$DOCKER_ENV_PATH" ] || [ "${HANGAR_ROTATE_SECRET_KEY:-0}" == "1" ]; then
        return 0
    fi
    calendar=$(envSetting ENABLE_GOOGLE_CALENDAR_CAPACITY 0)
    if [ "$calendar" != "1" ]; then
        return 0
    fi
    current=$(envSetting SECRET_KEY "")
    # shellcheck disable=SC2086
    if [ -n "$current" ] && ! isListed "$current" $insecure_secret_keys; then
        return 0
    fi
    echo "ERROR: SECRET_KEY in plane.env is empty or a published template value, and ENABLE_GOOGLE_CALENDAR_CAPACITY=1." >&2
    echo "This upgrade replaces SECRET_KEY, and Google Calendar capacity derives stored identifiers from it:" >&2
    echo "trainers' calendar selections stop matching until they are saved again, and trainings imported from" >&2
    echo "Google are seen as new occurrences, so their links to sessions have to be made again." >&2
    echo "Read 'Replacing a template SECRET_KEY with Google Calendar capacity' in the README, then run the upgrade" >&2
    echo "again with HANGAR_ROTATE_SECRET_KEY=1. Nothing has been changed." >&2
    return 1
}

# Replaces secrets that are empty or a value a template shipped, after
# syncEnvFile has carried the previous plane.env over. The two lists must match
# _INSECURE_SECRET_KEYS in apps/api/plane/settings/common.py and the lists in
# apps/api/bin/docker-entrypoint-common.sh and apps/live/src/env.ts.
function generateSecrets() {
    local insecure_secret_keys="60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5 change-this-key-on-deployment"
    local insecure_live_secret_keys="htbqvBJAgpm9bzvf3r4urJer0ENReatceh change-this-key-on-deployment secret-key"
    local name list current replacement

    # The API and Live refuse to start with these empty or on a template value,
    # and a new value costs one sign-in, so they are replaced on every run.
    for name in SECRET_KEY LIVE_SERVER_SECRET_KEY; do
        list=$insecure_secret_keys
        if [ "$name" == "LIVE_SERVER_SECRET_KEY" ]; then
            list=$insecure_live_secret_keys
        fi
        current=$(envSetting "$name" "")
        # shellcheck disable=SC2086
        if [ -n "$current" ] && ! isListed "$current" $list; then
            continue
        fi
        replacement=$(randomSecret 50)
        if [ ${#replacement} -ne 50 ]; then
            echo "Failed to generate $name. Exiting..." >&2
            exit 1
        fi
        updateEnvFile "$name" "$replacement" "$DOCKER_ENV_PATH"
        if [ -n "$current" ]; then
            echo "NOTICE: $name was a published template value and has been replaced in plane.env. Everybody is signed out once and signs in again." >&2
        else
            echo "Generated $name in plane.env" >&2
        fi
    done

    keepLegacyConnection DATABASE_URL "postgresql://plane:plane@plane-db/plane" \
        "plane:plane@plane-db:5432/plane" \
        "$(envSetting POSTGRES_USER plane):$(envSetting POSTGRES_PASSWORD plane)@$(envSetting PGHOST plane-db):$(envSetting POSTGRES_PORT 5432)/$(envSetting POSTGRES_DB plane)"
    keepLegacyConnection AMQP_URL "amqp://plane:plane@plane-mq:5672/plane" \
        "plane:plane@plane-mq:5672/plane" \
        "$(envSetting RABBITMQ_USER plane):$(envSetting RABBITMQ_PASSWORD plane)@$(envSetting RABBITMQ_HOST plane-mq):$(envSetting RABBITMQ_PORT 5672)/$(envSetting RABBITMQ_VHOST plane)"

    generateServicePassword POSTGRES_PASSWORD DATABASE_URL pgdata
    generateServicePassword RABBITMQ_PASSWORD AMQP_URL rabbitmq_data
}

# Swarm keeps a volume on whichever node ran its service, so a volume missing
# on this node proves nothing once a stack has run: an earlier plane.env counts
# as an existing deployment.
function isNewDeployment() {
    if [ "$PREVIOUS_ENV_EXISTS" == "1" ]; then
        return 1
    fi
    dataVolumeExists "$1"
    [ $? -eq 1 ]
}

# Release verification, the same in install.sh and swarm.sh. Every release
# after hangar-v0.1.0 publishes SHA256SUMS over its assets and
# SHA256SUMS.sigstore.json, the Cosign keyless signature the release workflow
# made for that tag. Files are downloaded into a scratch directory and checked
# there; the caller moves them into place only when this succeeds.

# Downloads $1 to $2 and prints the HTTP status, 000 when nothing answered.
# Leaves no file behind unless the status is 200.
function fetchAsset() {
    local url=$1 dest=$2 status
    status=$(curl -sSfL -H 'Cache-Control: no-cache, no-store' -o "$dest" -w '%{http_code}' "$url?$(date +%s)" 2>/dev/null)
    status=${status:-000}
    if [ "$status" != "200" ]; then
        rm -f "$dest"
    fi
    echo "$status"
}

# Prints the SHA-256 of file $1: sha256sum, or shasum on macOS.
function sha256Of() {
    local sum
    if command -v sha256sum >/dev/null 2>&1; then
        sum=$(sha256sum "$1" | awk '{ print $1 }')
    elif command -v shasum >/dev/null 2>&1; then
        sum=$(shasum -a 256 "$1" | awk '{ print $1 }')
    else
        echo "ERROR: neither sha256sum nor shasum is installed, so the release files cannot be verified." >&2
        return 1
    fi
    if [ -z "$sum" ]; then
        echo "ERROR: could not compute the SHA-256 of $1." >&2
        return 1
    fi
    echo "$sum"
}

# Returns 0 when APP_RELEASE is newer than v0.1.0. Every such release
# publishes SHA256SUMS, so a missing one is refused rather than tolerated.
function releasePublishesChecksums() {
    local version=${APP_RELEASE#v}
    version=${version%%-*}
    if ! [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        return 1
    fi
    local major=$((10#${BASH_REMATCH[1]})) minor=$((10#${BASH_REMATCH[2]})) patch=$((10#${BASH_REMATCH[3]}))
    [ "$major" -gt 0 ] || [ "$minor" -gt 1 ] || { [ "$minor" -eq 1 ] && [ "$patch" -gt 0 ]; }
}

# Checks the Cosign signature of $1/SHA256SUMS. The signer is fixed here, never
# read from a downloaded file: whoever could replace the assets could replace
# that file too.
function verifyChecksumSignature() {
    local dir=$1 status
    local identity="https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/hangar-$APP_RELEASE"
    local issuer="https://token.actions.githubusercontent.com"
    if ! command -v cosign >/dev/null 2>&1; then
        if [ "$HANGAR_REQUIRE_SIGNATURE" == "1" ]; then
            echo "ERROR: cosign is not installed, and HANGAR_REQUIRE_SIGNATURE=1 requires the signature of SHA256SUMS to be checked." >&2
            echo "Install cosign (https://docs.sigstore.dev/cosign/system_config/installation/) and run this again." >&2
            return 1
        fi
        echo "WARNING: cosign is not installed, so the signature of SHA256SUMS was not checked; the files were compared only with the checksum list downloaded beside them." >&2
        echo "Install cosign (https://docs.sigstore.dev/cosign/system_config/installation/) to have it checked, or check it by hand as" >&2
        echo "'Verifying release assets' describes: https://github.com/szymczag/hangar#verifying-release-assets" >&2
        echo "Set HANGAR_REQUIRE_SIGNATURE=1 to refuse files whose signature is not checked." >&2
        return 0
    fi
    status=$(fetchAsset "$RELEASE_DOWNLOAD_URL/hangar-$APP_RELEASE/SHA256SUMS.sigstore.json" "$dir/SHA256SUMS.sigstore.json")
    if [ "$status" != "200" ]; then
        echo "ERROR: release hangar-$APP_RELEASE publishes SHA256SUMS, but its signature SHA256SUMS.sigstore.json could not be downloaded (HTTP $status)." >&2
        return 1
    fi
    if ! cosign verify-blob \
        --bundle "$dir/SHA256SUMS.sigstore.json" \
        --certificate-identity "$identity" \
        --certificate-oidc-issuer "$issuer" \
        "$dir/SHA256SUMS" >&2; then
        echo "ERROR: SHA256SUMS of release hangar-$APP_RELEASE is not signed by $identity." >&2
        return 1
    fi
    echo "SHA256SUMS is signed by the Hangar release workflow for hangar-$APP_RELEASE."
}

# Checks the files named after $1, in directory $1, against the SHA256SUMS of
# release APP_RELEASE, after checking its signature.
function verifyReleaseAssets() {
    local dir=$1 name expected actual status
    shift
    status=$(fetchAsset "$RELEASE_DOWNLOAD_URL/hangar-$APP_RELEASE/SHA256SUMS" "$dir/SHA256SUMS")
    if [ "$status" == "404" ] && ! releasePublishesChecksums; then
        if [ "$HANGAR_REQUIRE_SIGNATURE" == "1" ]; then
            echo "ERROR: release hangar-$APP_RELEASE publishes no SHA256SUMS, and HANGAR_REQUIRE_SIGNATURE=1 refuses files it cannot verify." >&2
            return 1
        fi
        echo "WARNING: release hangar-$APP_RELEASE publishes no SHA256SUMS (releases up to hangar-v0.1.0 predate it), so the downloaded files are not verified." >&2
        return 0
    fi
    if [ "$status" == "404" ]; then
        echo "ERROR: release hangar-$APP_RELEASE has no SHA256SUMS, although every release after hangar-v0.1.0 publishes one. The files are refused." >&2
        return 1
    fi
    if [ "$status" != "200" ]; then
        echo "ERROR: SHA256SUMS of release hangar-$APP_RELEASE could not be downloaded (HTTP $status)." >&2
        return 1
    fi
    verifyChecksumSignature "$dir" || return 1
    for name in "$@"; do
        expected=$(awk -v name="$name" '{ file = $2; sub(/^\*/, "", file) } file == name { print $1; exit }' "$dir/SHA256SUMS")
        if [ -z "$expected" ]; then
            echo "ERROR: $name is not listed in SHA256SUMS of release hangar-$APP_RELEASE." >&2
            return 1
        fi
        actual=$(sha256Of "$dir/$name") || return 1
        if [ "$actual" != "$expected" ]; then
            echo "ERROR: $name does not match SHA256SUMS of release hangar-$APP_RELEASE (listed $expected, downloaded $actual)." >&2
            return 1
        fi
    done
    echo "Verified $* against SHA256SUMS of release hangar-$APP_RELEASE."
}

# Downloads the files named after $2 from $2 into $1. A name ending in '?' is
# optional: when it cannot be downloaded, that is reported and skipped.
function fetchAssets() {
    local dir=$1 base=$2 name file status
    shift 2
    for name in "$@"; do
        file=${name%\?}
        status=$(fetchAsset "$base/$file" "$dir/$file")
        if [ "$status" == "200" ]; then
            continue
        fi
        if [ "$file" != "$name" ]; then
            echo "WARNING: $file could not be downloaded from $base/ (HTTP $status); continuing without it." >&2
            continue
        fi
        echo "Failed to download $file from $base/ (HTTP $status)." >&2
        return 1
    done
}

# Downloads the deployment files named after $1 into the empty directory $1
# and verifies them. They come from release APP_RELEASE. Only when the operator
# set BRANCH, and the release cannot be downloaded, do they come from that
# branch instead, unverified. Nothing is written outside $1.
function downloadReleaseAssets() {
    local dir=$1 name present=()
    shift
    echo "Downloading the deployment files of release hangar-$APP_RELEASE from $RELEASE_DOWNLOAD_URL/hangar-$APP_RELEASE/"
    if ! fetchAssets "$dir" "$RELEASE_DOWNLOAD_URL/hangar-$APP_RELEASE" "$@"; then
        if [ -z "$BRANCH_REQUESTED" ]; then
            echo "ERROR: release hangar-$APP_RELEASE could not be downloaded from $RELEASE_DOWNLOAD_URL/. Check that it is published" >&2
            echo "and reachable, or set BRANCH=<branch> to install the files of that branch instead, unverified." >&2
            return 1
        fi
        if [ "$HANGAR_REQUIRE_SIGNATURE" == "1" ]; then
            echo "ERROR: release hangar-$APP_RELEASE could not be downloaded, and HANGAR_REQUIRE_SIGNATURE=1 refuses the unverified files of branch $BRANCH." >&2
            return 1
        fi
        rm -f "$dir"/*
        echo "WARNING: release hangar-$APP_RELEASE could not be downloaded. Using the files of branch $BRANCH from $FALLBACK_DOWNLOAD_URL/ because BRANCH is set; they are not verified." >&2
        fetchAssets "$dir" "$FALLBACK_DOWNLOAD_URL" "$@"
        return $?
    fi
    for name in "$@"; do
        name=${name%\?}
        if [ -f "$dir/$name" ]; then
            present+=("$name")
        fi
    done
    verifyReleaseAssets "$dir" "${present[@]}"
}

function download() {
    checkSecretKeyRotation || exit 1
    cd $SCRIPT_DIR || exit 1
    # Fetched and verified in a scratch directory first, so a failed or
    # tampered download leaves the deployment as it was.
    local staging
    staging=$(mktemp -d "$PLANE_INSTALL_DIR/.download.XXXXXX") || exit 1
    if ! downloadReleaseAssets "$staging" docker-compose.yml variables.env; then
        rm -rf "$staging"
        echo "Nothing in $PLANE_INSTALL_DIR has been changed. Exiting..."
        exit 1
    fi

    TS=$(date +%s)
    PREVIOUS_COMPOSE_PATH=""
    PREVIOUS_ENV_EXISTS=0
    # The stack name prefixes the volume names; getStackName defaults to plane.
    DEPLOYMENT_NAME=${stack_name:-plane}
    if [ -f "$PLANE_INSTALL_DIR/docker-compose.yml" ]; then
        mv $PLANE_INSTALL_DIR/docker-compose.yml $PLANE_INSTALL_DIR/archive/$TS.docker-compose.yml
        PREVIOUS_COMPOSE_PATH=$PLANE_INSTALL_DIR/archive/$TS.docker-compose.yml
    fi
    mv "$staging/docker-compose.yml" "$PLANE_INSTALL_DIR/docker-compose.yml"
    moveEnvFile "$staging/variables.env" "$PLANE_INSTALL_DIR/variables-upgrade.env"
    rm -rf "$staging"

    if [ -f "$DOCKER_ENV_PATH" ];
    then
        PREVIOUS_ENV_EXISTS=1
        copyEnvFile "$DOCKER_ENV_PATH" "$PLANE_INSTALL_DIR/archive/$TS.env" || exit 1
        copyEnvFile "$DOCKER_ENV_PATH" "$PLANE_INSTALL_DIR/plane.env.bak" || exit 1
    fi

    moveEnvFile "$PLANE_INSTALL_DIR/variables-upgrade.env" "$DOCKER_ENV_PATH" || exit 1

    syncEnvFile
    generateStorageCredentials
    generateSecrets

    updateEnvFile "APP_RELEASE" "$APP_RELEASE" "$DOCKER_ENV_PATH"

}
# docker-compose.yml orders its services with the long depends_on form, which
# docker stack deploy rejects ("depends_on must be a list") although it ignores
# depends_on anyway. Deploy a copy without those blocks.
function writeStackFile() {
    awk '
        /^    depends_on:[[:space:]]*$/ { skip = 1; next }
        skip && /^      / { next }
        { skip = 0; print }
    ' "$DOCKER_FILE_PATH" > "$STACK_FILE_PATH"
}

function deployStack() {   
    # Check if docker compose file and env file exist
    if [ ! -f "$DOCKER_FILE_PATH" ] || [ ! -f "$DOCKER_ENV_PATH" ]; then
        echo "Configuration files not found"
        echo "Downloading it now......"
        if [ -n "$HANGAR_RELEASE" ]; then
            APP_RELEASE=${HANGAR_RELEASE#hangar-}
        else
            APP_RELEASE=$(checkLatestRelease) || exit 1
        fi
        download
    fi
    if [ -z "$stack_name" ]; then
        getStackName
    fi
    echo "Starting ${stack_name} stack..."

    # Pull envs 
    if [ -f "$DOCKER_ENV_PATH" ]; then
        set -o allexport; source $DOCKER_ENV_PATH; set +o allexport;
    else
        echo "Environment file not found: $DOCKER_ENV_PATH"
        exit 1
    fi

    # Deploy the stack
    if ! writeStackFile; then
        echo "Failed to write $STACK_FILE_PATH"
        exit 1
    fi
    docker stack deploy -c $STACK_FILE_PATH $stack_name

    echo "Waiting for services to be deployed..."
    sleep 10

    # Check migrator service
    local migrator_service=$(docker service ls --filter name=${stack_name}_migrator -q)
    if [ -n "$migrator_service" ]; then
        echo ">> Waiting for Data Migration to finish"
        while docker service ls --filter name=${stack_name}_migrator | grep -q "running"; do
            echo -n "."
            sleep 1
        done
        echo ""
        
        # Get the most recent container for the migrator service
        local migrator_container=$(docker ps -a --filter name=${stack_name}_migrator --latest -q)
        
        if [ -n "$migrator_container" ]; then
            # Get the exit code of the container
            local exit_code=$(docker inspect --format='{{.State.ExitCode}}' $migrator_container)
            
            if [ "$exit_code" != "0" ]; then
                echo "Server failed to start ❌"
                echo "Migration failed with exit code: $exit_code"
                echo "Please check the logs for the 'migrator' service and resolve the issue(s)."
                echo "Stop the services by running the command: ./swarm.sh stop"
                exit 1
            else
                echo "   Data Migration completed successfully ✅"
            fi
        else
            echo "Warning: Could not find migrator container to check exit status"
        fi
    fi

    # Check API service
    local api_service=$(docker service ls --filter name=${stack_name}_api -q)
    while docker service ls --filter name=${stack_name}_api | grep -q "running"; do
        local running_container=$(docker ps --filter "name=${stack_name}_api" --filter "status=running" -q)
        if [ -n "$running_container" ]; then
            if docker container logs $running_container 2>/dev/null | grep -q "Application Startup Complete"; then
                break
            fi
        fi
        sleep 2
    done

    if [ -z "$api_service" ]; then
        echo "Hangar Server failed to start ❌"
        echo "Please check the logs for the 'api' service and resolve the issue(s)."
        echo "Stop the services by running the command: ./swarm.sh stop"
        exit 1
    fi
    echo "   Hangar Server started successfully ✅"
    echo ""
    echo "   You can access the application at $WEB_URL"
    echo ""
}

function removeStack() {
    if [ -z "$stack_name" ]; then
        echo "Stack name not found"
        exit 1
    fi
    echo "Removing ${stack_name} stack..."
    docker stack rm "$stack_name"
    echo "Waiting for services to be removed..."
    while docker stack ls | grep -q "$stack_name"; do
        sleep 1
    done
    sleep 20
    echo "Services stopped successfully ✅"
}

function viewStatus() {
    echo "Checking status of ${stack_name} stack..."
    if [ -z "$stack_name" ]; then
        echo "Stack name not found"
        exit 1
    fi
    docker stack ps "$stack_name"
}

function redeployStack() {   
    removeStack
    echo "ReDeploying ${stack_name} stack..."
    deployStack
}

function upgrade() {

    echo "Checking status of ${stack_name} stack..."
    if [ -z "$stack_name" ]; then
        echo "Stack name not found"
        exit 1
    fi
    
    checkSecretKeyRotation || exit 1
    local latest_release
    if [ -n "$HANGAR_RELEASE" ]; then
        latest_release=${HANGAR_RELEASE#hangar-}
    else
        latest_release=$(checkLatestRelease) || exit 1
    fi

    echo ""
    echo "Current release: $APP_RELEASE"

    if [ "$latest_release" == "$APP_RELEASE" ]; then
        echo ""
        echo "You are already using the latest release"
        exit 0
    fi

    echo "Latest release: $latest_release"
    echo ""

    # Check for confirmation to upgrade
    if [ "$HANGAR_ASSUME_YES" == "1" ]; then
        echo "Upgrading to the latest release ($latest_release) without asking (HANGAR_ASSUME_YES=1)."
    else
        echo "Do you want to upgrade to the latest release ($latest_release)?"
        read -p "Continue? [y/N]: " confirm

        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            echo "Exiting..."
            exit 0
        fi
    fi

    export APP_RELEASE=$latest_release

    # check if stack exists
    echo "Upgrading ${stack_name} stack..."

    # check env file and take backup
    if [ -f "$DOCKER_ENV_PATH" ]; then
        copyEnvFile "$DOCKER_ENV_PATH" "${DOCKER_ENV_PATH}.bak" || exit 1
    fi

    download

    # The bundled object storage moved from MinIO to SeaweedFS, which cannot
    # read MinIO's volume. Swarm volumes are local to a node, so the copy has to
    # run on the node that holds the legacy volume, with the stack removed.
    if docker volume inspect "${stack_name}_uploads" >/dev/null 2>&1 \
        && ! docker volume inspect "${stack_name}_object-storage" >/dev/null 2>&1; then
        removeStack
        echo ""
        echo "Uploads are still in the legacy MinIO volume '${stack_name}_uploads'."
        echo "On the node that holds it, download migrate-object-storage.sh from the"
        echo "$APP_RELEASE release assets and run:"
        echo "    ./migrate-object-storage.sh --project ${stack_name} --env-file $DOCKER_ENV_PATH"
        echo "then deploy the stack again. The stack was left removed."
        exit 1
    fi

    redeployStack
}

function viewSpecificLogs() {
    local service=$1
    
    # Input validation
    if [ -z "$service" ]; then
        echo "Error: Please specify a service name"
        return 1
    fi

    # Main loop for service logs
    while true; do
        # Get all running containers for the service
        local running_containers=$(docker ps --filter "name=${stack_name}_${service}" --filter "status=running" -q)

        # If no running containers found, try service logs
        if [ -z "$running_containers" ]; then
            echo "No running containers found for ${stack_name}_${service}, checking service logs..."
            if docker service inspect ${stack_name}_${service} >/dev/null 2>&1; then
                echo "Press Ctrl+C or 'q' to exit logs"
                docker service logs ${stack_name}_${service} -f
                break
            else
                echo "Error: No running containers or services found for ${stack_name}_${service}"
                return 1
            fi
            return
        fi

        # If multiple containers are running, let user choose
        if [ $(echo "$running_containers" | grep -v '^$' | wc -l) -gt 1 ]; then
            clear
            echo "Multiple containers found for ${stack_name}_${service}:"
            local i=1
            # Use regular arrays instead of associative arrays
            container_ids=()
            container_names=()
            
            while read -r container_id; do
                if [ -n "$container_id" ]; then
                    local container_name=$(docker inspect --format '{{.Name}}' "$container_id" | sed 's/\///')
                    container_ids[$i]=$container_id
                    container_names[$i]=$container_name
                    echo "[$i] ${container_names[$i]} (${container_ids[$i]})"
                    i=$((i+1))
                fi
            done <<< "$running_containers"
            
            echo -e "\nPlease select a container number:"
            read -r selection

            if [[ "$selection" =~ ^[0-9]+$ ]] && [ -n "${container_ids[$selection]}" ]; then
                local selected_container=${container_ids[$selection]}
                clear
                echo "Showing logs for container: ${container_names[$selection]}"
                echo "Press Ctrl+C or 'q' to return to container selection"
                
                # Start watching logs in the background
                docker container logs -f "$selected_container" &
                local log_pid=$!
                
                while true; do
                    read -r -n 1 input
                    if [[ $input == "q" ]]; then
                        kill $log_pid 2>/dev/null
                        wait $log_pid 2>/dev/null
                        break
                    fi
                done
                clear
            else
                echo "Error: Invalid selection"
                sleep 2
            fi
        else
            # Single container case
            local container_name=$(docker inspect --format '{{.Name}}' "$running_containers" | sed 's/\///')
            echo "Showing logs for container: $container_name"
            echo "Press Ctrl+C or 'q' to exit logs"
            docker container logs -f "$running_containers" &
            local log_pid=$!
            
            while true; do
                read -r -n 1 input
                if [[ $input == "q" ]]; then
                    kill $log_pid 2>/dev/null
                    wait $log_pid 2>/dev/null
                    break
                fi
            done
            break
        fi
    done
}

function viewLogs(){
    
    ARG_SERVICE_NAME=$2
    if [ -z "$ARG_SERVICE_NAME" ];
    then
        echo
        echo "Select a Service you want to view the logs for:"
        echo "   1) Web"
        echo "   2) Space"
        echo "   3) API"
        echo "   4) Worker"
        echo "   5) Beat-Worker"
        echo "   6) Migrator"
        echo "   7) Proxy"
        echo "   8) Redis"
        echo "   9) Postgres"
        echo "   10) Object Storage"
        echo "   11) RabbitMQ"
        echo "   0) Back to Main Menu"
        echo 
        read -p "Service: " DOCKER_SERVICE_NAME 

        until (( DOCKER_SERVICE_NAME >= 0 && DOCKER_SERVICE_NAME <= 11 )); do
            echo "Invalid selection. Please enter a number between 0 and 11."
            read -p "Service: " DOCKER_SERVICE_NAME
        done

        if [ -z "$DOCKER_SERVICE_NAME" ];
        then
            echo "INVALID SERVICE NAME SUPPLIED"
        else
            case $DOCKER_SERVICE_NAME in
                1) viewSpecificLogs "web";;
                2) viewSpecificLogs "space";;
                3) viewSpecificLogs "api";;
                4) viewSpecificLogs "worker";;
                5) viewSpecificLogs "beat-worker";;
                6) viewSpecificLogs "migrator";;
                7) viewSpecificLogs "proxy";;
                8) viewSpecificLogs "plane-redis";;
                9) viewSpecificLogs "plane-db";;
                10) viewSpecificLogs "plane-minio";;
                11) viewSpecificLogs "plane-mq";;
                0) askForAction;;
                *) echo "INVALID SERVICE NAME SUPPLIED";;
            esac
        fi
    elif [ -n "$ARG_SERVICE_NAME" ];
    then
        ARG_SERVICE_NAME=$(echo "$ARG_SERVICE_NAME" | tr '[:upper:]' '[:lower:]')
        case $ARG_SERVICE_NAME in
            web) viewSpecificLogs "web";;
            space) viewSpecificLogs "space";;
            api) viewSpecificLogs "api";;
            worker) viewSpecificLogs "worker";;
            beat-worker) viewSpecificLogs "beat-worker";;
            migrator) viewSpecificLogs "migrator";;
            proxy) viewSpecificLogs "proxy";;
            redis) viewSpecificLogs "plane-redis";;
            postgres) viewSpecificLogs "plane-db";;
            minio) viewSpecificLogs "plane-minio";;
            rabbitmq) viewSpecificLogs "plane-mq";;
            *) echo "INVALID SERVICE NAME SUPPLIED";;
        esac
    else
        echo "INVALID SERVICE NAME SUPPLIED"
    fi
}



function askForAction() {
    # Rest of askForAction remains the same but use $stack_name instead of $STACK_NAME
    local DEFAULT_ACTION=$1

    if [ -z "$DEFAULT_ACTION" ]; then
        echo
        echo "Select an Action you want to perform:"
        echo "   1) Deploy Stack"
        echo "   2) Remove Stack"
        echo "   3) View Stack Status"
        echo "   4) Redeploy Stack"
        echo "   5) Upgrade"
        echo "   6) View Logs"
        echo "   7) Exit"
        echo 
        read -p "Action [3]: " ACTION
        until [[ -z "$ACTION" || "$ACTION" =~ ^[1-7]$ ]]; do
            echo "$ACTION: invalid selection."
            read -p "Action [3]: " ACTION
        done

        if [ -z "$ACTION" ]; then
            ACTION=3
        fi
        echo
    fi

    if [ "$ACTION" == "1" ] || [ "$DEFAULT_ACTION" == "deploy" ]; then
        deployStack
    elif [ "$ACTION" == "2" ] || [ "$DEFAULT_ACTION" == "remove" ]; then
        removeStack
    elif [ "$ACTION" == "3" ] || [ "$DEFAULT_ACTION" == "status" ]; then
        viewStatus
    elif [ "$ACTION" == "4" ] || [ "$DEFAULT_ACTION" == "redeploy" ]; then
        redeployStack
    elif [ "$ACTION" == "5" ] || [ "$DEFAULT_ACTION" == "upgrade" ]; then
        upgrade
    elif [ "$ACTION" == "6" ] || [ "$DEFAULT_ACTION" == "logs" ]; then
        viewLogs "$@"
    elif [ "$ACTION" == "7" ] || [ "$DEFAULT_ACTION" == "exit" ]; then
        exit 0
    else
        echo "INVALID ACTION SUPPLIED"
    fi
}

# Initialize stack name at script start

if [ -z "$stack_name" ]; then
    readStackName
fi

# Sync environment variables
if [ -f "$DOCKER_ENV_PATH" ]; then
    DOCKERHUB_USER=$(getEnvValue "DOCKERHUB_USER" "$DOCKER_ENV_PATH")
    APP_RELEASE=$(getEnvValue "APP_RELEASE" "$DOCKER_ENV_PATH")
    # Images are tagged vX.Y.Z; the release tag adds a hangar- prefix.
    APP_RELEASE=${APP_RELEASE#hangar-}

    if [ -z "$DOCKERHUB_USER" ]; then
        DOCKERHUB_USER=ghcr.io/szymczag
        updateEnvFile "DOCKERHUB_USER" "$DOCKERHUB_USER" "$DOCKER_ENV_PATH"
    fi

    if [ -z "$APP_RELEASE" ]; then
        APP_RELEASE=stable
        updateEnvFile "APP_RELEASE" "$APP_RELEASE" "$DOCKER_ENV_PATH"
    fi
fi


# Main execution
# --yes / -y may appear anywhere among the arguments.
ACTION_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --yes|-y) HANGAR_ASSUME_YES=1 ;;
        *) ACTION_ARGS+=("$arg") ;;
    esac
done
set -- "${ACTION_ARGS[@]}"

print_header
protectEnvFiles
askForAction "$@"
