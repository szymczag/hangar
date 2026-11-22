#!/usr/bin/env bash

# BRANCH set by the operator is the only way deployment files may come from a
# branch rather than a release: when the release cannot be downloaded, and for
# a local image build. Without it, a failed release download is an error.
BRANCH_REQUESTED=${BRANCH:-}
BRANCH=${BRANCH:-preview}
SCRIPT_DIR=$PWD
SERVICE_FOLDER=plane-app
PLANE_INSTALL_DIR=$PWD/$SERVICE_FOLDER
export APP_RELEASE=stable
export DOCKERHUB_USER=ghcr.io/szymczag
export PULL_POLICY=${PULL_POLICY:-if_not_present}
export GH_REPO=szymczag/hangar
export RELEASE_DOWNLOAD_URL="https://github.com/$GH_REPO/releases/download"
export FALLBACK_DOWNLOAD_URL="https://raw.githubusercontent.com/$GH_REPO/$BRANCH/deployments/cli/community"
# The release this copy of the script was published with. The release
# workflow replaces "unreleased" with it (release_evidence.py stamp-scripts);
# see checkScriptRelease. The asset it is published as, and its path here.
SCRIPT_RELEASE=unreleased
SCRIPT_ASSET=setup.sh
SCRIPT_PATH=${BASH_SOURCE[0]:-$SCRIPT_ASSET}

CPU_ARCH=$(uname -m)
OS_NAME=$(uname)
UPPER_CPU_ARCH=$(tr '[:lower:]' '[:upper:]' <<< "$CPU_ARCH")

mkdir -p "$PLANE_INSTALL_DIR"
# Holds earlier copies of plane.env: owner only, like plane.env itself.
( umask 077 && mkdir -p "$PLANE_INSTALL_DIR/archive" )
DOCKER_FILE_PATH=$PLANE_INSTALL_DIR/docker-compose.yaml
# Written after a local image build; points the Hangar services at those images.
DOCKER_OVERRIDE_PATH=$PLANE_INSTALL_DIR/docker-compose.override.yaml
DOCKER_ENV_PATH=$PLANE_INSTALL_DIR/plane.env
MIGRATE_STORAGE_SCRIPT=$PLANE_INSTALL_DIR/migrate-object-storage.sh
# The Compose project name, which prefixes the volume names.
DEPLOYMENT_NAME=$SERVICE_FOLDER

# Unattended use:
#   HANGAR_ASSUME_YES=1 (or --yes) answers the upgrade prompt with yes, refuses
#   to fall back to a local image build, and does not clear the screen.
#   HANGAR_INSTALL_SOURCE_DIR=<dir> takes docker-compose.yml, variables.env and
#   migrate-object-storage.sh from <dir> (deployments/cli/community in a
#   checkout) instead of downloading them from the release.
#   HANGAR_RELEASE=vX.Y.Z installs or upgrades to that release instead of
#   asking the GitHub API for the latest one, which rate-limits anonymous use.
#   HANGAR_REQUIRE_SIGNATURE=1 refuses deployment files whose Cosign signature
#   cannot be checked: no cosign, a release without SHA256SUMS, a branch, or
#   HANGAR_INSTALL_SOURCE_DIR.
#   HANGAR_ALLOW_OLD_SCRIPT=1 (or --allow-old-script) lets install and upgrade
#   go to a release newer than this script, which they otherwise refuse.
HANGAR_ALLOW_OLD_SCRIPT=${HANGAR_ALLOW_OLD_SCRIPT:-0}
HANGAR_ASSUME_YES=${HANGAR_ASSUME_YES:-0}
HANGAR_INSTALL_SOURCE_DIR=${HANGAR_INSTALL_SOURCE_DIR:-}
HANGAR_RELEASE=${HANGAR_RELEASE:-}
HANGAR_REQUIRE_SIGNATURE=${HANGAR_REQUIRE_SIGNATURE:-0}
SCRIPT_RELEASE_WARNED=0
# Set by upgrade: the directory holding the verified files of the new release.
STAGED_DEPLOYMENT_DIR=""

function print_header() {
if [ "$HANGAR_ASSUME_YES" != "1" ] && [ -t 1 ]; then
    clear
fi

cat <<"EOF"
##+.    ##+    .##-                  
 ######+.######-.######.              
 #######.   -###    +#####+.          
 #######.      +       +######.       
 #######.              .#######       
 #######.              .#######       
  #######       +      .#######       
    .+#####+    ###-   .#######       
        .######.-#####+.+######       
            -##.    -##    .+##
EOF
}

function spinner() {
    local pid=$1
    local delay=.5
    local spinstr='|/-\'

    if ! ps -p "$pid" > /dev/null; then  
        echo "Invalid PID: $pid"  
        return 1  
    fi  
    while ps -p "$pid" > /dev/null; do  
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr" >&2
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b" >&2
    done
    printf "    \b\b\b\b" >&2
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

function initialize(){
    printf "Please wait while we check the availability of Docker images for the selected release ($APP_RELEASE) with ${UPPER_CPU_ARCH} support." >&2

    if [ "$CUSTOM_BUILD" == "true" ]; then
        echo "" >&2
        echo "" >&2
        echo "${UPPER_CPU_ARCH} images are not available for selected release ($APP_RELEASE)." >&2
        echo "build"
        return 1
    fi

    local IMAGE_NAME=ghcr.io/szymczag/hangar-proxy
    local IMAGE_TAG=${APP_RELEASE}
    docker manifest inspect "${IMAGE_NAME}:${IMAGE_TAG}" | grep -q "\"architecture\": \"${CPU_ARCH}\"" &
    local pid=$!
    spinner "$pid"
    
    echo "" >&2

    wait "$pid"

    if [ $? -eq 0 ]; then
        echo "Hangar supports ${CPU_ARCH}" >&2
        echo "available"
        return 0
    else
        echo "" >&2
        echo "" >&2
        echo "${UPPER_CPU_ARCH} images are not available for selected release ($APP_RELEASE)." >&2
        echo "" >&2
        echo "build"
        return 1
    fi
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

function updateCustomVariables(){
    echo "Updating custom variables..." >&2
    updateEnvFile "DOCKERHUB_USER" "$DOCKERHUB_USER" "$DOCKER_ENV_PATH"
    updateEnvFile "APP_RELEASE" "$APP_RELEASE" "$DOCKER_ENV_PATH"
    updateEnvFile "PULL_POLICY" "$PULL_POLICY" "$DOCKER_ENV_PATH"
    updateEnvFile "CUSTOM_BUILD" "$CUSTOM_BUILD" "$DOCKER_ENV_PATH"
    echo "Custom variables updated successfully" >&2
}

function syncEnvFile(){
    echo "Syncing environment variables..." >&2
    if [ -f "$PLANE_INSTALL_DIR/plane.env.bak" ]; then
        updateCustomVariables
        
        # READ keys of plane.env and update the values from plane.env.bak
        while IFS= read -r line
        do
            # ignore is the line is empty or starts with #
            if [ -z "$line" ] || [[ $line == \#* ]]; then
                continue
            fi
            key=$(echo "$line" | cut -d'=' -f1)
            value=$(getEnvValue "$key" "$PLANE_INSTALL_DIR/plane.env.bak")
            if [ -n "$value" ]; then
                updateEnvFile "$key" "$value" "$DOCKER_ENV_PATH"
            fi
        done < "$DOCKER_ENV_PATH"
    fi
    echo "Environment variables synced successfully" >&2
}

# Builds the Hangar images from the source of Git ref $1 (the release tag, or
# the branch the operator named) as myplane/hangar-<image>:local.
function buildYourOwnImage(){
    local source_ref=$1
    echo "Building images locally from $source_ref..."

    export DOCKERHUB_USER="myplane"
    export APP_RELEASE="local"
    export PULL_POLICY="never"
    CUSTOM_BUILD="true"

    # checkout the code to ~/tmp/plane folder and build the images
    local PLANE_TEMP_CODE_DIR=~/tmp/plane
    rm -rf $PLANE_TEMP_CODE_DIR
    mkdir -p $PLANE_TEMP_CODE_DIR
    REPO=https://github.com/$GH_REPO.git
    if ! git clone "$REPO" "$PLANE_TEMP_CODE_DIR" --branch "$source_ref" --single-branch --depth 1; then
        echo "Failed to check out $source_ref of $REPO. Exiting..."
        exit 1
    fi

    cd "$PLANE_TEMP_CODE_DIR" || exit

    # build.yml takes its build contexts relative to its own directory.
    bash -c "$COMPOSE_CMD -f $PLANE_TEMP_CODE_DIR/deployments/cli/community/build.yml build --no-cache"  >&2
    if [ $? -ne 0 ]; then
        echo "Build failed. Exiting..."
        exit 1
    fi
    echo "Build completed successfully"
    echo ""
    echo "You can now start the services by running the command: ./setup.sh start"
    echo ""
}

function install() {
    echo "Begin Installing Hangar"
    echo ""

    if [ -n "$HANGAR_RELEASE" ]; then
        APP_RELEASE=${HANGAR_RELEASE#hangar-}
        export APP_RELEASE
    elif [ "$APP_RELEASE" == "stable" ] || [ "$APP_RELEASE" == "local" ]; then
        # "local" names the images of a local build, not a release.
        # exit inside checkLatestRelease only leaves the $(...) subshell
        APP_RELEASE=$(checkLatestRelease) || exit 1
        export APP_RELEASE
    fi
    checkScriptRelease "$APP_RELEASE" install || exit 1

    local build_image=$(initialize)

    if [ "$build_image" == "build" ]; then
        if [ "$HANGAR_ASSUME_YES" == "1" ]; then
            echo "Images for this architecture are not published; not building them unattended. Exiting..."
            exit 1
        fi
        # ask for confirmation to continue building the images
        echo "Do you want to continue with building the Docker images locally?"
        read -p "Continue? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            echo "Exiting..."
            exit 0
        fi
    fi

    if [ "$build_image" == "build" ]; then
        download "true"
    else
        download "false"
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

# A deployment is new when Docker reports no volume of that kind for it.
function isNewDeployment() {
    dataVolumeExists "$1"
    [ $? -eq 1 ]
}

# Copies the deployment files from HANGAR_INSTALL_SOURCE_DIR into $1 instead
# of downloading them.
function copyLocalAssets() {
    local dir=$1 name
    for name in docker-compose.yml variables.env migrate-object-storage.sh; do
        if [ ! -f "$HANGAR_INSTALL_SOURCE_DIR/$name" ]; then
            echo "$name not found in $HANGAR_INSTALL_SOURCE_DIR"
            return 1
        fi
        cp "$HANGAR_INSTALL_SOURCE_DIR/$name" "$dir/$name" || return 1
    done
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

# Puts docker-compose.yml, variables.env and migrate-object-storage.sh into
# the empty directory $1: copied from HANGAR_INSTALL_SOURCE_DIR, or downloaded
# from the release and verified.
function stageDeploymentFiles() {
    local dir=$1
    if [ -n "$HANGAR_INSTALL_SOURCE_DIR" ]; then
        if [ "$HANGAR_REQUIRE_SIGNATURE" == "1" ]; then
            echo "ERROR: HANGAR_REQUIRE_SIGNATURE=1 refuses the unverified files of HANGAR_INSTALL_SOURCE_DIR." >&2
            return 1
        fi
        echo "Using the deployment files in $HANGAR_INSTALL_SOURCE_DIR (HANGAR_INSTALL_SOURCE_DIR); they are not verified against a release."
        copyLocalAssets "$dir"
        return $?
    fi
    downloadReleaseAssets "$dir" docker-compose.yml variables.env "migrate-object-storage.sh?"
}

# Script release check, the same in install.sh and swarm.sh. The script does
# not update itself: install and upgrade fetch a release's deployment files,
# never a newer copy of the script, so a fix that lives in the script reaches
# a deployment only when its operator runs the new script. A published script
# knows its own release (SCRIPT_RELEASE, stamped by the release workflow); one
# from a branch or a checkout says "unreleased" and is not checked.

# Compares releases $1 and $2 (vX.Y.Z, or vX.Y.Z-<pre-release>) and prints -1,
# 0 or 1 as $1 is older than, the same as, or newer than $2. A pre-release
# precedes its release. Prints nothing and returns 1 when either is not a
# release version.
function compareReleases() {
    local pattern='^v?([0-9]+)\.([0-9]+)\.([0-9]+)(-([0-9A-Za-z.]+))?$'
    local left=() right=() left_pre right_pre i a b
    [[ "$1" =~ $pattern ]] || return 1
    left=("${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}")
    left_pre=${BASH_REMATCH[5]}
    [[ "$2" =~ $pattern ]] || return 1
    right=("${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}")
    right_pre=${BASH_REMATCH[5]}
    for i in 0 1 2; do
        a=$((10#${left[i]}))
        b=$((10#${right[i]}))
        if [ "$a" -lt "$b" ]; then echo -1; return 0; fi
        if [ "$a" -gt "$b" ]; then echo 1; return 0; fi
    done
    if [ "$left_pre" == "$right_pre" ]; then echo 0; return 0; fi
    if [ -z "$left_pre" ]; then echo 1; return 0; fi
    if [ -z "$right_pre" ]; then echo -1; return 0; fi
    # Pre-releases compare identifier by identifier: numbers as numbers,
    # anything else as text; when all shared ones match, fewer comes first.
    IFS=. read -r -a left <<< "$left_pre"
    IFS=. read -r -a right <<< "$right_pre"
    for ((i = 0; i < ${#left[@]} && i < ${#right[@]}; i++)); do
        a=${left[i]}
        b=${right[i]}
        [ "$a" == "$b" ] && continue
        if [[ "$a" =~ ^[0-9]+$ && "$b" =~ ^[0-9]+$ ]]; then
            if [ $((10#$a)) -lt $((10#$b)) ]; then echo -1; else echo 1; fi
        elif [[ "$a" < "$b" ]]; then
            echo -1
        else
            echo 1
        fi
        return 0
    done
    if [ ${#left[@]} -lt ${#right[@]} ]; then echo -1; else echo 1; fi
}

# Returns 0 when release $1 is newer than this script's own release, so it
# ships a newer script. An unreleased script, or a target that is not a
# release version ("stable", "local"), is never outdated.
function scriptIsOutdatedFor() {
    local order
    [ "$SCRIPT_RELEASE" == "unreleased" ] && return 1
    order=$(compareReleases "${1#hangar-}" "$SCRIPT_RELEASE") || return 1
    [ "$order" == "1" ]
}

# Prints the commands that replace this script with the verified one of
# release $1. The certificate identity is written here, as in
# verifyChecksumSignature, never read from a downloaded file.
function printScriptUpdateSteps() {
    local release=$1
    local tag="hangar-$release"
    local base="$RELEASE_DOWNLOAD_URL/$tag"
    local identity="https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/$tag"
    {
        echo "Replace it with the $SCRIPT_ASSET of $tag and check it before running it:"
        echo ""
        echo "    mkdir -p $tag && cd $tag"
        echo "    curl -fsSL -O $base/$SCRIPT_ASSET -O $base/SHA256SUMS -O $base/SHA256SUMS.sigstore.json"
        echo "    cosign verify-blob --bundle SHA256SUMS.sigstore.json \\"
        echo "        --certificate-identity $identity \\"
        echo "        --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS"
        echo "    sha256sum --check --ignore-missing SHA256SUMS   # macOS: shasum -a 256 --check --ignore-missing SHA256SUMS"
        echo "    cd .. && cp $tag/$SCRIPT_ASSET $SCRIPT_PATH && chmod 755 $SCRIPT_PATH"
        echo ""
        echo "or let '$SCRIPT_PATH update-script' download and verify it the same way; it does not run it."
    } >&2
}

# install and upgrade (swarm.sh: deploy and upgrade) call this with the
# release they are about to fetch, action $2, before they change anything.
# A release newer than the script is refused unless HANGAR_ALLOW_OLD_SCRIPT=1.
# The same or an older release (a rollback) goes ahead.
function checkScriptRelease() {
    local target=${1#hangar-} action=$2
    scriptIsOutdatedFor "$target" || return 0
    if [ "$HANGAR_ALLOW_OLD_SCRIPT" == "1" ]; then
        if [ "$SCRIPT_RELEASE_WARNED" != "1" ]; then
            echo "WARNING: this $SCRIPT_ASSET is from hangar-$SCRIPT_RELEASE and hangar-$target ships a newer one; continuing with it because HANGAR_ALLOW_OLD_SCRIPT=1. Changes in the newer script are not applied." >&2
            SCRIPT_RELEASE_WARNED=1
        fi
        return 0
    fi
    echo "ERROR: this $SCRIPT_ASSET is from release hangar-$SCRIPT_RELEASE, and hangar-$target ships a newer $SCRIPT_ASSET." >&2
    echo "The script does not update itself, and what the new one changes (how plane.env and its copies are protected," >&2
    echo "which secrets are replaced, how downloads are verified) applies only when you run it." >&2
    printScriptUpdateSteps "$target"
    echo "Then run the $action again with the new script. To $action with this script anyway, set HANGAR_ALLOW_OLD_SCRIPT=1" >&2
    echo "(or pass --allow-old-script). Nothing has been changed." >&2
    return 1
}

# Actions that only run what is installed warn, once, when the deployment is
# on a release newer than the script; they never refuse.
function warnScriptRelease() {
    local installed=${APP_RELEASE#hangar-}
    scriptIsOutdatedFor "$installed" || return 0
    [ "$SCRIPT_RELEASE_WARNED" == "1" ] && return 0
    SCRIPT_RELEASE_WARNED=1
    echo "WARNING: this $SCRIPT_ASSET is from hangar-$SCRIPT_RELEASE, but the deployment runs hangar-$installed, which ships a newer one." >&2
    echo "Run '$SCRIPT_PATH update-script', or replace it by hand as the README's 'Upgrading Hangar Version' describes." >&2
}

# Prints the owner and group of $1 as uid:gid: GNU stat, or BSD stat on macOS.
function fileOwner() {
    stat -c '%u:%g' "$1" 2>/dev/null || stat -f '%u:%g' "$1" 2>/dev/null
}

# update-script: replaces this script with the SCRIPT_ASSET of HANGAR_RELEASE,
# or of the latest release. It downloads into a scratch directory beside the
# script, verifies the file with the release's SHA256SUMS and its signature
# (verifyReleaseAssets, under the same HANGAR_REQUIRE_SIGNATURE policy as the
# deployment files), checks that it names that release, gives it mode 755 and
# the old script's owner, and renames it over the old script, so the old one
# stays whole until then. It never runs the new script.
function updateScript() {
    local target order dir staging status owner
    if [ -n "$HANGAR_RELEASE" ]; then
        target=${HANGAR_RELEASE#hangar-}
    else
        target=$(checkLatestRelease) || return 1
    fi
    if ! compareReleases "$target" "$target" >/dev/null; then
        echo "ERROR: '$target' is not a release version. Nothing has been changed." >&2
        return 1
    fi
    if [ "$SCRIPT_RELEASE" != "unreleased" ]; then
        order=$(compareReleases "$target" "$SCRIPT_RELEASE")
        if [ "$order" == "0" ]; then
            echo "$SCRIPT_PATH is already the $SCRIPT_ASSET of hangar-$target. Nothing has been changed."
            return 0
        fi
        if [ "$order" == "-1" ]; then
            echo "$SCRIPT_PATH is from hangar-$SCRIPT_RELEASE, newer than hangar-$target, and installs older releases too. Nothing has been changed."
            return 0
        fi
    fi
    if [ -L "$SCRIPT_PATH" ] || [ ! -f "$SCRIPT_PATH" ]; then
        echo "ERROR: $SCRIPT_PATH is not a regular file (a symbolic link, or a script read from a pipe), so it is not replaced." >&2
        printScriptUpdateSteps "$target"
        return 1
    fi
    # The verification functions read the release from APP_RELEASE.
    local APP_RELEASE=$target
    if ! releasePublishesChecksums; then
        echo "ERROR: release hangar-$target publishes no SHA256SUMS, so its $SCRIPT_ASSET cannot be verified. Nothing has been changed." >&2
        return 1
    fi
    dir=$(dirname "$SCRIPT_PATH")
    # Beside the script, so the final rename stays on one file system.
    staging=$(mktemp -d "$dir/.update-script.XXXXXX") || return 1
    status=$(fetchAsset "$RELEASE_DOWNLOAD_URL/hangar-$target/$SCRIPT_ASSET" "$staging/$SCRIPT_ASSET")
    if [ "$status" != "200" ]; then
        echo "ERROR: $SCRIPT_ASSET of release hangar-$target could not be downloaded (HTTP $status). $SCRIPT_PATH has not been changed." >&2
        rm -rf "$staging"
        return 1
    fi
    if ! verifyReleaseAssets "$staging" "$SCRIPT_ASSET"; then
        echo "$SCRIPT_PATH has not been changed." >&2
        rm -rf "$staging"
        return 1
    fi
    if ! grep -qxF "SCRIPT_RELEASE=$target" "$staging/$SCRIPT_ASSET"; then
        echo "ERROR: the $SCRIPT_ASSET of hangar-$target does not say it is from that release. $SCRIPT_PATH has not been changed." >&2
        rm -rf "$staging"
        return 1
    fi
    owner=$(fileOwner "$SCRIPT_PATH")
    if ! chmod 755 "$staging/$SCRIPT_ASSET" \
        || { [ "$(fileOwner "$staging/$SCRIPT_ASSET")" != "$owner" ] && ! chown "$owner" "$staging/$SCRIPT_ASSET" 2>/dev/null; }; then
        echo "ERROR: could not give the new $SCRIPT_ASSET mode 755 and the owner of $SCRIPT_PATH ($owner); run update-script as that user. $SCRIPT_PATH has not been changed." >&2
        rm -rf "$staging"
        return 1
    fi
    if ! mv -f "$staging/$SCRIPT_ASSET" "$SCRIPT_PATH"; then
        echo "ERROR: could not replace $SCRIPT_PATH. It has not been changed." >&2
        rm -rf "$staging"
        return 1
    fi
    rm -rf "$staging"
    echo "Replaced $SCRIPT_PATH with the verified $SCRIPT_ASSET of hangar-$target. It has not been run; run '$SCRIPT_PATH upgrade' (or the action you need) now."
}

function download() {
    local LOCAL_BUILD=$1 staging
    checkSecretKeyRotation || exit 1
    cd "$SCRIPT_DIR" || exit 1
    # Fetched and verified in a scratch directory first, so a failed or
    # tampered download leaves the deployment as it was. An upgrade stages
    # them before it stops the services and hands the directory over here.
    if [ -n "$STAGED_DEPLOYMENT_DIR" ] && [ -d "$STAGED_DEPLOYMENT_DIR" ]; then
        staging=$STAGED_DEPLOYMENT_DIR
    else
        staging=$(mktemp -d "$PLANE_INSTALL_DIR/.download.XXXXXX") || exit 1
    fi
    if [ "$staging" != "$STAGED_DEPLOYMENT_DIR" ] && ! stageDeploymentFiles "$staging"; then
        rm -rf "$staging"
        echo "Nothing in $PLANE_INSTALL_DIR has been changed. Exiting..."
        exit 1
    fi

    TS=$(date +%s)
    PREVIOUS_COMPOSE_PATH=""
    if [ -f "$PLANE_INSTALL_DIR/docker-compose.yaml" ]
    then
        mv $PLANE_INSTALL_DIR/docker-compose.yaml $PLANE_INSTALL_DIR/archive/$TS.docker-compose.yaml
        PREVIOUS_COMPOSE_PATH=$PLANE_INSTALL_DIR/archive/$TS.docker-compose.yaml
    fi
    mv "$staging/docker-compose.yml" "$PLANE_INSTALL_DIR/docker-compose.yaml"
    moveEnvFile "$staging/variables.env" "$PLANE_INSTALL_DIR/variables-upgrade.env"
    if [ -f "$staging/migrate-object-storage.sh" ]; then
        mv "$staging/migrate-object-storage.sh" "$MIGRATE_STORAGE_SCRIPT"
        chmod +x "$MIGRATE_STORAGE_SCRIPT"
    fi
    rm -rf "$staging"

    if [ -f "$DOCKER_ENV_PATH" ];
    then
        copyEnvFile "$DOCKER_ENV_PATH" "$PLANE_INSTALL_DIR/archive/$TS.env" || exit 1
        copyEnvFile "$DOCKER_ENV_PATH" "$PLANE_INSTALL_DIR/plane.env.bak" || exit 1
    fi

    moveEnvFile "$PLANE_INSTALL_DIR/variables-upgrade.env" "$DOCKER_ENV_PATH" || exit 1

    syncEnvFile
    generateStorageCredentials
    generateSecrets
    finishDownload "$LOCAL_BUILD"
}

# The Compose files of this deployment: docker-compose.yaml as the release
# published it and, after a local image build, the override that points the
# Hangar services at the images built here. Every compose command uses both.
function composeFiles() {
    if [ -f "$DOCKER_OVERRIDE_PATH" ]; then
        echo "-f $DOCKER_FILE_PATH -f $DOCKER_OVERRIDE_PATH"
    else
        echo "-f $DOCKER_FILE_PATH"
    fi
}

# A release's docker-compose.yml names every Hangar image by digest, which a
# local build cannot produce. Rather than edit the verified file, write an
# override that gives each service using a hangar-<image> the image built
# locally as $1/hangar-<image>:$2, and never pulls it.
function writeLocalBuildOverride() {
    local registry=$1 tag=$2 services
    services=$(awk -v registry="$registry" -v tag="$tag" '
        /^services:[[:space:]]*$/ { in_services = 1; next }
        /^[^[:space:]#]/ { in_services = 0 }
        in_services && /^  [A-Za-z0-9._-]+:[[:space:]]*$/ { service = $1; sub(/:$/, "", service); next }
        in_services && service != "" && /^    image:/ && match($0, /\/hangar-[a-z0-9-]+/) {
            printf "  %s:\n    image: %s/%s:%s\n    pull_policy: never\n", service, registry, substr($0, RSTART + 1, RLENGTH - 1), tag
            service = ""
        }
    ' "$DOCKER_FILE_PATH")
    if [ -z "$services" ]; then
        echo "No Hangar image found in $DOCKER_FILE_PATH to replace with the local build." >&2
        return 1
    fi
    {
        echo "# Written by setup.sh after building the Hangar images locally. It points"
        echo "# the Hangar services at those images instead of the digests the release"
        echo "# pinned in docker-compose.yaml. An install or upgrade that builds locally"
        echo "# writes it again; one that pulls the published images removes it."
        echo "services:"
        echo "$services"
    } > "$DOCKER_OVERRIDE_PATH"
    echo "Wrote $DOCKER_OVERRIDE_PATH for the locally built images."
}

function finishDownload() {
    local LOCAL_BUILD=$1
    if [ "$LOCAL_BUILD" == "true" ]; then
        # Build the source of the release just installed, or the branch named.
        local source_ref="hangar-$APP_RELEASE"
        if [ -n "$BRANCH_REQUESTED" ]; then
            source_ref=$BRANCH
        fi
        export DOCKERHUB_USER="myplane"
        export APP_RELEASE="local"
        export PULL_POLICY="never"
        CUSTOM_BUILD="true"

        buildYourOwnImage "$source_ref"

        if [ $? -ne 0 ]; then
            echo ""
            echo "Build failed. Exiting..."
            exit 1
        fi
        writeLocalBuildOverride "$DOCKERHUB_USER" "$APP_RELEASE" || exit 1
        updateCustomVariables
    else
        CUSTOM_BUILD="false"
        rm -f "$DOCKER_OVERRIDE_PATH"
        updateCustomVariables
        bash -c "$COMPOSE_CMD $(composeFiles) --env-file=$DOCKER_ENV_PATH pull --policy always"

        if [ $? -ne 0 ]; then
            echo ""
            echo "Failed to pull the images. Exiting..."
            exit 1
        fi
    fi
    
    echo ""
    echo "Most recent version of Hangar is now available for you to use"
    echo ""
    echo "In case of 'Upgrade', please check the 'plane.env 'file for any new variables and update them accordingly"
    echo ""
}
# The bundled object storage moved from MinIO to SeaweedFS, which cannot read
# MinIO's volume. Returns 0 when uploads still live only in the legacy volume.
function objectStorageMigrationPending() {
    [ "${SKIP_OBJECT_STORAGE_MIGRATION:-0}" == "1" ] && return 1
    if [ ! -x "$MIGRATE_STORAGE_SCRIPT" ]; then
        # Without the helper, fall back to the volume check alone.
        docker volume inspect "${SERVICE_FOLDER}_uploads" >/dev/null 2>&1 \
            && ! docker volume inspect "${SERVICE_FOLDER}_object-storage" >/dev/null 2>&1
        return $?
    fi
    "$MIGRATE_STORAGE_SCRIPT" --project "$SERVICE_FOLDER" --env-file "$DOCKER_ENV_PATH" --check
    [ $? -eq 3 ]
}
function migrateObjectStorage() {
    if [ ! -x "$MIGRATE_STORAGE_SCRIPT" ]; then
        echo "migrate-object-storage.sh is missing from $PLANE_INSTALL_DIR."
        echo "Run the upgrade again, or download it from the release assets."
        return 1
    fi
    "$MIGRATE_STORAGE_SCRIPT" --project "$SERVICE_FOLDER" --env-file "$DOCKER_ENV_PATH" "$@"
}
function startServices() {
    if objectStorageMigrationPending; then
        echo ""
        echo "Uploads are still in the legacy MinIO volume '${SERVICE_FOLDER}_uploads'."
        echo "Starting now would serve an empty object store. Migrate them first:"
        echo "    $0 migrate-storage"
        echo "(If this install uses external S3 storage instead, set SKIP_OBJECT_STORAGE_MIGRATION=1.)"
        exit 1
    fi
    bash -c "$COMPOSE_CMD $(composeFiles) --env-file=$DOCKER_ENV_PATH up -d --pull if_not_present --quiet-pull"

    local migrator_container_id=$(docker container ls -aq -f "name=$SERVICE_FOLDER-migrator")
    if [ -n "$migrator_container_id" ]; then
        local idx=0
        while docker inspect --format='{{.State.Status}}' $migrator_container_id | grep -q "running"; do
            local message=">> Waiting for Data Migration to finish"
            local dots=$(printf '%*s' $idx | tr ' ' '.')
            echo -ne "\r$message$dots"
            ((idx++))
            sleep 1
        done
    fi
    printf "\r\033[K"
    echo ""
    echo "   Data Migration completed successfully ✅"

    # if migrator exit status is not 0, show error message and exit
    if [ -n "$migrator_container_id" ]; then
        local migrator_exit_code=$(docker inspect --format='{{.State.ExitCode}}' $migrator_container_id)
        if [ $migrator_exit_code -ne 0 ]; then
            echo "Hangar Server failed to start ❌"
            # stopServices
            echo
            echo "Please check the logs for the 'migrator' service and resolve the issue(s)."
            echo "Stop the services by running the command: ./setup.sh stop"
            exit 1
        fi
    fi

    local api_container_id=$(docker container ls -q -f "name=$SERVICE_FOLDER-api")

    # Verify container exists
    if [ -z "$api_container_id" ]; then
        echo "   Error: API container not found. Please check if services are running."
        exit 1
    fi

    local idx2=0
    local api_ready=true        # assume success, flip on timeout
    local max_wait_time=300  # 5 minutes timeout
    local start_time=$(date +%s)

    echo "   Waiting for API Service to be ready..."
    while ! docker exec "$api_container_id" python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=3)" > /dev/null 2>&1; do
        local current_time=$(date +%s)
        local elapsed_time=$((current_time - start_time))

        if [ $elapsed_time -gt $max_wait_time ]; then
            echo ""
            echo "   API Service health check timed out after 5 minutes"
            echo "   Checking if API container is still running..."
            if docker ps | grep -q "$SERVICE_FOLDER-api"; then
                echo "   API container is running but did not pass the health-check. Continuing without marking it ready."
                api_ready=false
                break
            else
                echo "   API container is not running. Please check logs."
                exit 1
            fi
        fi

        local message=">> Waiting for API Service to Start (${elapsed_time}s)"
        local dots=$(printf '%*s' $idx2 | tr ' ' '.')
        echo -ne "\r$message$dots"
        ((idx2++))
        sleep 1
    done
    printf "\r\033[K"
    if [ "$api_ready" = true ]; then
        echo "   API Service started successfully ✅"
    else
        echo "   ⚠️  API Service did not respond to health-check – please verify manually."
    fi
    source "${DOCKER_ENV_PATH}"
    echo "   Hangar Server started successfully ✅"
    echo ""
    echo "   You can access the application at $WEB_URL"
    echo ""

}
function stopServices() {
    bash -c "$COMPOSE_CMD $(composeFiles) --env-file=$DOCKER_ENV_PATH down"
}
function restartServices() {
    stopServices
    startServices
}
function upgrade() {
    local latest_release
    checkSecretKeyRotation || exit 1
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
        warnScriptRelease
        exit 0
    fi

    echo "Latest release: $latest_release"
    echo ""
    # Before the prompt, so a refusal leaves everything as it was.
    checkScriptRelease "$latest_release" upgrade || exit 1

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

    echo "Upgrading Hangar to the latest release..."
    echo ""

    # Download and verify the new release while the installed one keeps
    # running, so a download that fails or does not verify leaves it running.
    echo "***** DOWNLOADING AND VERIFYING RELEASE $latest_release ****"
    STAGED_DEPLOYMENT_DIR=$(mktemp -d "$PLANE_INSTALL_DIR/.download.XXXXXX") || exit 1
    trap 'rm -rf "$STAGED_DEPLOYMENT_DIR"' EXIT
    if ! stageDeploymentFiles "$STAGED_DEPLOYMENT_DIR"; then
        echo "Nothing in $PLANE_INSTALL_DIR has been changed, and the services were not stopped. Exiting..."
        exit 1
    fi

    echo
    echo "***** STOPPING SERVICES ****"
    stopServices

    echo
    echo "***** DOWNLOADING STABLE VERSION ****"
    install

    if objectStorageMigrationPending; then
        echo
        echo "***** MIGRATING OBJECT STORAGE (MinIO -> SeaweedFS) ****"
        migrateObjectStorage || {
            echo "Object storage migration failed; the services were left stopped."
            exit 1
        }
    fi

    echo "***** PLEASE VALIDATE AND START SERVICES ****"
}
function viewSpecificLogs(){
    local SERVICE_NAME=$1

    if bash -c "$COMPOSE_CMD $(composeFiles) ps | grep -q '$SERVICE_NAME'"; then
        echo "Service '$SERVICE_NAME' is running."
    else
        echo "Service '$SERVICE_NAME' is not running."
    fi

    bash -c "$COMPOSE_CMD $(composeFiles) logs -f $SERVICE_NAME"
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
function backup_container_dir() {
    local BACKUP_FOLDER=$1
    local CONTAINER_NAME=$2
    local CONTAINER_DATA_DIR=$3
    local SERVICE_FOLDER=$4

    echo "Backing up $CONTAINER_NAME data..."
    local CONTAINER_ID=$(bash -c "$COMPOSE_CMD $(composeFiles) ps -q $CONTAINER_NAME")
    if [ -z "$CONTAINER_ID" ]; then
        echo "Error: $CONTAINER_NAME container not found. Make sure the services are running."
        return 1
    fi

    # Create a temporary directory for the backup
    mkdir -p "$BACKUP_FOLDER/$SERVICE_FOLDER"

    # Copy the data directory from the running container
    echo "Copying $CONTAINER_NAME data directory..."
    docker cp -q "$CONTAINER_ID:$CONTAINER_DATA_DIR/." "$BACKUP_FOLDER/$SERVICE_FOLDER/"
    local cp_status=$?

    if [ $cp_status -ne 0 ]; then
        echo "Error: Failed to copy $SERVICE_FOLDER data"
        rm -rf $BACKUP_FOLDER/$SERVICE_FOLDER
        return 1
    fi

    # Create tar.gz of the data
    cd "$BACKUP_FOLDER"
    tar -czf "${SERVICE_FOLDER}.tar.gz" "$SERVICE_FOLDER/"
    local tar_status=$?
    if [ $tar_status -eq 0 ]; then
        rm -rf "$SERVICE_FOLDER/"
    fi
    cd - > /dev/null

    if [ $tar_status -ne 0 ]; then
        echo "Error: Failed to create tar archive"
        return 1
    fi

    echo "Successfully backed up $SERVICE_FOLDER data"
}

function backupData() {
    local datetime=$(date +"%Y%m%d-%H%M")
    local BACKUP_FOLDER=$PLANE_INSTALL_DIR/backup/$datetime
    # The archives hold the database, uploads and broker state, so they and
    # their directories are for the owner only. Backup is the last action
    # of this run, so the umask is not restored.
    umask 077
    mkdir -p "$BACKUP_FOLDER" || exit 1
    restrictToOwner "$PLANE_INSTALL_DIR/backup"

    # Check if docker-compose.yml exists
    if [ ! -f "$DOCKER_FILE_PATH" ]; then
        echo "Error: docker-compose.yml not found at $DOCKER_FILE_PATH"
        exit 1
    fi

    backup_container_dir "$BACKUP_FOLDER" "plane-db" "/var/lib/postgresql/data" "pgdata" || exit 1
    backup_container_dir "$BACKUP_FOLDER" "plane-minio" "/data" "object-storage" || exit 1
    backup_container_dir "$BACKUP_FOLDER" "plane-mq" "/var/lib/rabbitmq" "rabbitmq_data" || exit 1
    backup_container_dir "$BACKUP_FOLDER" "plane-redis" "/data" "redisdata" || exit 1

    echo ""
    echo "Backup completed successfully. Backup files are stored in $BACKUP_FOLDER"
    echo ""
}
function askForAction() {
    local DEFAULT_ACTION=$1

    if [ -z "$DEFAULT_ACTION" ];
    then
        echo
        echo "Select a Action you want to perform:"
        echo "   1) Install"
        echo "   2) Start"
        echo "   3) Stop"
        echo "   4) Restart"
        echo "   5) Upgrade"
        echo "   6) View Logs"
        echo "   7) Backup Data"
        echo "   8) Migrate Object Storage (MinIO -> SeaweedFS)"
        echo "   9) Exit"
        echo 
        read -p "Action [2]: " ACTION
        until [[ -z "$ACTION" || "$ACTION" =~ ^[1-9]$ ]]; do
            echo "$ACTION: invalid selection."
            read -p "Action [2]: " ACTION
        done

        if [ -z "$ACTION" ];
        then
            ACTION=2
        fi
        echo
    fi

    if [ "$ACTION" == "1" ] || [ "$DEFAULT_ACTION" == "install" ];
    then
        install
        # askForAction
    elif [ "$ACTION" == "2" ] || [ "$DEFAULT_ACTION" == "start" ];
    then
        warnScriptRelease
        startServices
        # askForAction
    elif [ "$ACTION" == "3" ] || [ "$DEFAULT_ACTION" == "stop" ];
    then
        warnScriptRelease
        stopServices
        # askForAction
    elif [ "$ACTION" == "4" ] || [ "$DEFAULT_ACTION" == "restart" ];
    then
        warnScriptRelease
        restartServices
        # askForAction
    elif [ "$ACTION" == "5" ]  || [ "$DEFAULT_ACTION" == "upgrade" ];
    then
        upgrade
        # askForAction
    elif [ "$ACTION" == "6" ]  || [ "$DEFAULT_ACTION" == "logs" ];
    then
        viewLogs "$@"
        askForAction
    elif [ "$ACTION" == "7" ]  || [ "$DEFAULT_ACTION" == "backup" ];
    then
        backupData
    elif [ "$ACTION" == "8" ]  || [ "$DEFAULT_ACTION" == "migrate-storage" ];
    then
        migrateObjectStorage
    elif [ "$DEFAULT_ACTION" == "update-script" ]
    then
        updateScript || exit 1
    elif [ "$ACTION" == "9" ]
    then
        exit 0
    else
        echo "INVALID ACTION SUPPLIED"
    fi
}

# if docker-compose is installed
if command -v docker-compose &> /dev/null
then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

if [ "$CPU_ARCH" == "x86_64" ] || [ "$CPU_ARCH" == "amd64" ]; then
    CPU_ARCH="amd64"
elif [ "$CPU_ARCH" == "aarch64" ] || [ "$CPU_ARCH" == "arm64" ]; then
    CPU_ARCH="arm64"
fi

if [ -f "$DOCKER_ENV_PATH" ]; then
    DOCKERHUB_USER=$(getEnvValue "DOCKERHUB_USER" "$DOCKER_ENV_PATH")
    APP_RELEASE=$(getEnvValue "APP_RELEASE" "$DOCKER_ENV_PATH")
    # Images are tagged vX.Y.Z; the release tag adds a hangar- prefix.
    APP_RELEASE=${APP_RELEASE#hangar-}
    PULL_POLICY=$(getEnvValue "PULL_POLICY" "$DOCKER_ENV_PATH")
    CUSTOM_BUILD=$(getEnvValue "CUSTOM_BUILD" "$DOCKER_ENV_PATH")

    if [ -z "$DOCKERHUB_USER" ]; then
        DOCKERHUB_USER=ghcr.io/szymczag
        updateEnvFile "DOCKERHUB_USER" "$DOCKERHUB_USER" "$DOCKER_ENV_PATH"
    fi

    if [ -z "$APP_RELEASE" ]; then
        APP_RELEASE=stable
        updateEnvFile "APP_RELEASE" "$APP_RELEASE" "$DOCKER_ENV_PATH"
    fi

    if [ -z "$PULL_POLICY" ]; then
        PULL_POLICY=if_not_present
        updateEnvFile "PULL_POLICY" "$PULL_POLICY" "$DOCKER_ENV_PATH"
    fi

    if [ -z "$CUSTOM_BUILD" ]; then
        CUSTOM_BUILD=false
        updateEnvFile "CUSTOM_BUILD" "$CUSTOM_BUILD" "$DOCKER_ENV_PATH"
    fi
fi

# --yes / -y and --allow-old-script may appear anywhere among the arguments.
ACTION_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --yes|-y) HANGAR_ASSUME_YES=1 ;;
        --allow-old-script) HANGAR_ALLOW_OLD_SCRIPT=1 ;;
        *) ACTION_ARGS+=("$arg") ;;
    esac
done
set -- "${ACTION_ARGS[@]}"

print_header
protectEnvFiles
askForAction "$@"
