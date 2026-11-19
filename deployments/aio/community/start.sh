#!/bin/bash -e

# Secrets the container generates are kept on the data volume, not in the
# container layer, so recreating the container does not replace them. A new
# SECRET_KEY would sign everybody out and make saved instance settings
# unreadable.
SECRETS_FILE="${HANGAR_SECRETS_FILE:-/app/data/secrets.env}"

# Template values a deployment must never run with. They match
# _INSECURE_SECRET_KEYS in apps/api/plane/settings/common.py and
# INSECURE_LIVE_SERVER_SECRET_KEYS in apps/live/src/env.ts; a test keeps the
# lists in step.
INSECURE_SECRET_KEYS=("60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5"
                      "change-this-key-on-deployment")
INSECURE_LIVE_SERVER_SECRET_KEYS=("htbqvBJAgpm9bzvf3r4urJer0ENReatceh"
                                  "change-this-key-on-deployment"
                                  "secret-key")

print_header(){
    clear
    echo "------------------------------------------------"
    echo "Hangar Community (All-In-One)"
    echo "------------------------------------------------"
    echo ""
    echo "You are required to pass below environment variables to the script"
    echo "    DOMAIN_NAME, DATABASE_URL, REDIS_URL, AMQP_URL"
    echo "    AWS_REGION, AWS_ACCESS_KEY_ID"
    echo "    AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET_NAME"
    echo ""
    echo "Other optional environment variables: "
    echo "    SITE_ADDRESS (default: ':80')"
    echo "    FILE_SIZE_LIMIT (default: 5242880)"
    echo "    APP_PROTOCOL (http or https)"
    echo "    SECRET_KEY (generated on first boot if not set, kept in /app/data)"
    echo "    LIVE_SERVER_SECRET_KEY (generated on first boot if not set, kept in /app/data)"
    echo ""
    echo ""
}

check_required_env(){
    echo "Checking required environment variables..."
    local keys=("DOMAIN_NAME" "DATABASE_URL" "REDIS_URL" "AMQP_URL" 
                "AWS_REGION" "AWS_ACCESS_KEY_ID" "AWS_SECRET_ACCESS_KEY" "AWS_S3_BUCKET_NAME")
    
    local missing_keys=()
    # Check if the environment variable is set and not empty
    for key in "${keys[@]}"; do
        if [ -z "${!key}" ]; then
            echo "  ❌  '$key' is not set or is empty"
            missing_keys+=("$key")
        fi
    done

    if [ ${#missing_keys[@]} -gt 0 ]; then
        echo ""
        exit 1
    fi
    # add checkmark
    echo "✅ Required environment variables are available"
    echo ""
}

# Set key=value in an env file, adding the key when it is missing. awk reads
# the key and the value from its environment, so &, |, \ and spaces in a value
# are written verbatim (sed would interpret them).
set_file_value(){
    local file="$1"
    local key="$2"
    local value="$3"

    if ! grep -q "^$key=" "$file"; then
        printf '%s=%s\n' "$key" "$value" >> "$file"
        return 0
    fi
    (
        umask 077
        SFV_KEY="$key" SFV_VAL="$value" awk '
            index($0, ENVIRON["SFV_KEY"] "=") == 1 { print ENVIRON["SFV_KEY"] "=" ENVIRON["SFV_VAL"]; next }
            { print }
        ' "$file" > "$file.tmp"
    ) && mv "$file.tmp" "$file"
}

# The value of key in an env file, or nothing.
read_file_value(){
    local file="$1"
    local key="$2"
    [ -f "$file" ] || return 0
    { grep -m1 "^$key=" "$file" || true; } | cut -d'=' -f2-
}

update_env_value(){
    local key="$1"
    local value="$2"

    # check if the file exists
    if [ ! -f "plane.env" ]; then
        echo "plane.env file not found"
        exit 1
    fi

    # add a missing key; replace an existing one only with a non-empty value
    if ! grep -q "^$key=" plane.env || [ -n "$value" ]; then
        set_file_value plane.env "$key" "$value"
    fi
}

# Succeeds when the first argument is set and is none of the others.
is_usable_secret(){
    local value="$1"
    shift
    [ -n "$value" ] || return 1
    local insecure
    for insecure in "$@"; do
        [ "$value" = "$insecure" ] && return 1
    done
    return 0
}

generate_secret(){
    tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c50
}

store_secret(){
    local key="$1"
    local value="$2"
    if mkdir -p "$(dirname "$SECRETS_FILE")" &&
        ( umask 077; touch "$SECRETS_FILE" ) &&
        chmod 600 "$SECRETS_FILE" &&
        set_file_value "$SECRETS_FILE" "$key" "$value"; then
        return 0
    fi
    echo "Could not write $SECRETS_FILE; /app/data must be a writable volume" >&2
    return 1
}

# Print the secret to run with, from the first source that holds a value other
# than a template one:
#   1. the environment;
#   2. plane.env, where an operator may have set it, and where a container
#      started before secrets moved to the data volume kept the one it
#      generated. If the data volume holds none yet, the value is copied there,
#      so the next container keeps it;
#   3. the data volume, which holds the value generated on first boot;
#   4. otherwise a new value, kept on the data volume.
resolve_secret(){
    local key="$1"
    shift
    local value="${!key}"
    if is_usable_secret "$value" "$@"; then
        printf '%s' "$value"
        return 0
    fi

    local stored
    stored=$(read_file_value "$SECRETS_FILE" "$key")
    value=$(read_file_value plane.env "$key")
    if is_usable_secret "$value" "$@"; then
        if ! is_usable_secret "$stored" "$@"; then
            echo "Keeping the existing $key in $SECRETS_FILE" >&2
            store_secret "$key" "$value" || return 1
        fi
        printf '%s' "$value"
        return 0
    fi

    if is_usable_secret "$stored" "$@"; then
        printf '%s' "$stored"
        return 0
    fi

    echo "Generating $key and keeping it in $SECRETS_FILE" >&2
    value=$(generate_secret)
    store_secret "$key" "$value" || return 1
    printf '%s' "$value"
}

# Export every KEY=value line of plane.env as is. The value is not word-split,
# so spaces survive; one pair of surrounding quotes is removed, as the commented
# examples in variables.env write them.
export_env_file(){
    local line key value
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ""|\#*|"="*) continue ;;
            *=*)
                key="${line%%=*}"
                value="${line#*=}"
                if [ ${#value} -ge 2 ]; then
                    case "$value" in
                        \"*\"|\'*\') value="${value:1:${#value}-2}" ;;
                    esac
                fi
                export "$key=$value"
                ;;
        esac
    done < plane.env
}

check_pre_requisites(){
    check_required_env

    # check if the file exists
    if [ ! -f "plane.env" ]; then
        echo "plane.env file not found"
        exit 1
    fi
    # add a new line to the end of the file
    echo "" >> plane.env
    echo "" >> plane.env
    echo "✅ Pre-requisites checked"
    echo ""
    
}

validate_domain_name() {
    local domain="$1"

    # An optional :port, for an instance published on another port than 80 or
    # 443; WEB_URL and CORS_ALLOWED_ORIGINS then carry it.
    if [[ "$domain" =~ ^(.+):([0-9]{1,5})$ ]]; then
        domain="${BASH_REMATCH[1]}"
        local port=$((10#${BASH_REMATCH[2]}))
        if (( port < 1 || port > 65535 )); then
            echo "INVALID"
            return 1
        fi
    fi
    
    # Check if it's an IP address first
    if [[ "$domain" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "IP"
        return 0
    fi
    
    # FQDN validation regex
    local fqdn_regex='^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.?$'
    
    if [[ "$domain" =~ $fqdn_regex ]]; then
        # Additional checks
        if [[ ${#domain} -le 253 ]] && [[ ! "$domain" =~ \.\. ]] && [[ ! "$domain" =~ ^- ]] && [[ ! "$domain" =~ -\. ]]; then
            echo "FQDN"
            return 0
        fi
    fi
    
    echo "INVALID"
    return 1
}

update_env_file(){
    echo "Updating environment file..."
    # check if DOMAIN_NAME is valid IP address
    local domain_type=$(validate_domain_name "$DOMAIN_NAME")
    if [ "$domain_type" == "INVALID" ]; then
        echo "DOMAIN_NAME is not a valid FQDN or IP address, optionally followed by :port"
        exit 1
    fi

    local app_protocol=${APP_PROTOCOL:-http}
    
    update_env_value "APP_PROTOCOL" "$app_protocol"
    update_env_value "DOMAIN_NAME" "$DOMAIN_NAME"
    update_env_value "APP_DOMAIN" "$DOMAIN_NAME"
    if [ -n "$SITE_ADDRESS" ]; then
        update_env_value "SITE_ADDRESS" "$SITE_ADDRESS"
    else
        update_env_value "SITE_ADDRESS" ":80"
    fi
    update_env_value "WEB_URL" "$app_protocol://$DOMAIN_NAME"
    update_env_value "CORS_ALLOWED_ORIGINS" "http://$DOMAIN_NAME,https://$DOMAIN_NAME"

    # update database url
    update_env_value "DATABASE_URL" "$DATABASE_URL"
    update_env_value "REDIS_URL" "$REDIS_URL"
    update_env_value "REDIS_SSL_CERT_REQS" "$REDIS_SSL_CERT_REQS"
    update_env_value "REDIS_SSL_CA_CERTS" "$REDIS_SSL_CA_CERTS"
    update_env_value "AMQP_URL" "$AMQP_URL"
    
    # update aws credentials
    update_env_value "AWS_REGION" "$AWS_REGION"
    update_env_value "AWS_ACCESS_KEY_ID" "$AWS_ACCESS_KEY_ID"
    update_env_value "AWS_SECRET_ACCESS_KEY" "$AWS_SECRET_ACCESS_KEY"
    update_env_value "AWS_S3_BUCKET_NAME" "$AWS_S3_BUCKET_NAME"
    update_env_value "AWS_S3_ENDPOINT_URL" "${AWS_S3_ENDPOINT_URL:-https://s3.${AWS_REGION}.amazonaws.com}"
    update_env_value "BUCKET_NAME" "$AWS_S3_BUCKET_NAME"
    update_env_value "USE_MINIO" "0"

    # Optional environment variables
    # SECRET_KEY and LIVE_SERVER_SECRET_KEY: an explicit value wins; otherwise
    # the one generated on first boot, kept on the data volume.
    SECRET_KEY=$(resolve_secret SECRET_KEY "${INSECURE_SECRET_KEYS[@]}")
    update_env_value "SECRET_KEY" "$SECRET_KEY"
    update_env_value "FILE_SIZE_LIMIT" "${FILE_SIZE_LIMIT:-5242880}"
    LIVE_SERVER_SECRET_KEY=$(resolve_secret LIVE_SERVER_SECRET_KEY "${INSECURE_LIVE_SERVER_SECRET_KEYS[@]}")
    update_env_value "LIVE_SERVER_SECRET_KEY" "$LIVE_SERVER_SECRET_KEY"

    update_env_value "API_KEY_RATE_LIMIT" "${API_KEY_RATE_LIMIT:-60/minute}"

    echo "✅ Environment file updated"
    echo ""
}

# Join the non-empty arguments with single spaces.
join_sources(){
    local joined="" source
    for source in "$@"; do
        [ -n "$source" ] && joined="${joined:+$joined }$source"
    done
    printf '%s' "$joined"
}

# Web and God Mode are served here by Caddy from the static builds of the web
# and admin images, so the security headers those images' nginx sends are
# rendered from the same generated templates and start-up hook
# (render-security-headers.py). The object-storage origin is added to the
# policy like the Helm chart does, because uploads are not proxied through this
# origin; space reads the same variables. A failure stops the container.
configure_security_headers(){
    local dir="${HANGAR_SECURITY_HEADERS_DIR:-/app/proxy/security-headers}"
    local renderer="${HANGAR_SECURITY_HEADERS_RENDERER:-/app/proxy/render-security-headers.py}"
    local web_root="${HANGAR_WEB_ROOT:-/app/web}"
    local admin_root="${HANGAR_ADMIN_ROOT:-/app/admin}"
    local storage
    storage=$(python3 "$renderer" storage-origin)

    HANGAR_CSP_IMG_SRC=$(join_sources "$storage" "${HANGAR_CSP_IMG_SRC-}")
    HANGAR_CSP_CONNECT_SRC=$(join_sources "$storage" "${HANGAR_CSP_CONNECT_SRC-}")
    HANGAR_CSP_MEDIA_SRC=$(join_sources "$storage" "${HANGAR_CSP_MEDIA_SRC-}")
    export HANGAR_CSP_IMG_SRC HANGAR_CSP_CONNECT_SRC HANGAR_CSP_MEDIA_SRC

    (
        # The hook also creates nginx's output directory, which nothing reads here.
        . "$dir/15-hangar-csp.envsh"
        python3 "$renderer" render --template "$dir/web.conf.template" --out "$dir/web.caddy" \
            --root "$web_root" --pristine "$dir/pristine/web"
        python3 "$renderer" render --template "$dir/admin.conf.template" --out "$dir/admin.caddy" \
            --root "$admin_root" --pristine "$dir/pristine/admin"
    )
    echo "✅ Security headers rendered for web and God Mode"
    echo ""
}

main(){
    print_header
    check_pre_requisites
    update_env_file

    # load plane.env as exported variables
    export_env_file

    configure_security_headers

    # Recreate log dirs at boot. A host bind of /app/logs replaces the
    # directories baked into the image, and supervisord refuses to start
    # if stdout_logfile's parent path is missing.
    mkdir -p /app/logs/access /app/logs/error

    /usr/local/bin/supervisord -c /etc/supervisor/conf.d/supervisor.conf
}

main "$@"