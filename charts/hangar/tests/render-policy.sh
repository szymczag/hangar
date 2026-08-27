#!/usr/bin/env bash

set -euo pipefail

chart_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "$chart_dir/../.." && pwd)"
tmp_parent="${TMPDIR:-$repo_root/.local/chart-tests}"
mkdir -p "$tmp_parent"
tmp_dir="$(mktemp -d "$tmp_parent/render-policy.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT

production_render="$tmp_dir/production.yaml"
evaluation_render="$tmp_dir/evaluation.yaml"
boundary_render="$tmp_dir/boundary.yaml"
gateway_render="$tmp_dir/gateway.yaml"
evaluation_gateway_render="$tmp_dir/evaluation-gateway.yaml"
traefik_render="$tmp_dir/traefik.yaml"
imports_render="$tmp_dir/imports.yaml"
kube_version="${KUBE_VERSION:-1.36.2}"

fail() {
    echo "render-policy: $*" >&2
    exit 1
}

assert_absent() {
    local pattern="$1"
    local file="$2"
    local description="$3"

    if grep -Eq "$pattern" "$file"; then
        fail "$description"
    fi
}

assert_present() {
    local pattern="$1"
    local file="$2"
    local description="$3"

    if ! grep -Eq "$pattern" "$file"; then
        fail "$description"
    fi
}

assert_invalid() {
    local description="$1"
    shift

    if helm template invalid "$chart_dir" --namespace hangar --kube-version "$kube_version" "$@" >/dev/null 2>&1; then
        fail "schema accepted invalid values: $description"
    fi
}

# Exercise both declared compatibility edges and reject adjacent unsupported
# minors so Chart.yaml cannot drift away from the tested range.
helm template minimum-kubernetes "$chart_dir" --namespace hangar --kube-version 1.30.0 >/dev/null
for unsupported_kube_version in 1.29.0 1.37.0; do
    if helm template unsupported-kubernetes "$chart_dir" \
        --namespace hangar \
        --kube-version "$unsupported_kube_version" >/dev/null 2>&1; then
        fail "Chart.yaml accepted unsupported Kubernetes $unsupported_kube_version"
    fi
done

helm lint "$chart_dir" --kube-version "$kube_version"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" >"$production_render"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" \
    --values "$chart_dir/ci/evaluation-values.yaml" >"$evaluation_render"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" \
    --set application.fileSizeLimit=1073741824 \
    --set application.signedUrlExpiration=86400 \
    --set application.hardDeleteAfterDays=3650 \
    --set-string 'live.pdfAssetAllowedHosts[0]=storage.internal' >"$boundary_render"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" \
    --set gateway.enabled=true \
    --set gateway.create=true \
    --set-string gateway.name=public-mtls \
    --set-string networkPolicy.ingressController.preset=envoyGateway >"$gateway_render"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" \
    --values "$chart_dir/ci/evaluation-values.yaml" \
    --set gateway.enabled=true \
    --set gateway.create=true \
    --set-string gateway.name=public-mtls \
    --set-string networkPolicy.ingressController.preset=envoyGateway >"$evaluation_gateway_render"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" \
    --set-string networkPolicy.ingressController.preset=traefik >"$traefik_render"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" \
    --set todoistImports.enabled=true \
    --set todoistImports.worker.replicas=2 \
    --set todoistImports.worker.pdb.enabled=true >"$imports_render"
helm template custom "$chart_dir" --namespace hangar --kube-version "$kube_version" \
    --set-string networkPolicy.ingressController.preset=custom \
    --set-string 'networkPolicy.ingressController.namespaceSelector.matchLabels.kubernetes\.io/metadata\.name=edge-system' \
    --set-string networkPolicy.ingressController.podSelector.matchLabels.app=edge-proxy >/dev/null

for render in "$production_render" "$evaluation_render" "$imports_render"; do
    image_count="$(grep -Ec '^[[:space:]]+image:' "$render")"
    restricted_count="$(grep -Ec '^[[:space:]]+allowPrivilegeEscalation: false$' "$render")"
    readonly_count="$(grep -Ec '^[[:space:]]+readOnlyRootFilesystem: true$' "$render")"

    [[ "$image_count" -gt 0 ]] || fail "no container images found in $render"
    [[ "$restricted_count" -eq "$image_count" ]] || fail "every container must disable privilege escalation in $render"
    [[ "$readonly_count" -eq "$image_count" ]] || fail "every container must use a read-only root filesystem in $render"

    while IFS= read -r image_line; do
        [[ "$image_line" == *@sha256:* ]] || fail "mutable image reference in $render: $image_line"
    done < <(grep -E '^[[:space:]]+image:' "$render")

    assert_absent '^[[:space:]]+hostPath:' "$render" "hostPath volumes are forbidden in $render"
    assert_absent '^kind: (Role|RoleBinding|ClusterRole|ClusterRoleBinding)$' "$render" "application RBAC is forbidden in $render"
    assert_absent '^automountServiceAccountToken: true$|^[[:space:]]+automountServiceAccountToken: true$' "$render" "service-account token automounting must never be enabled in $render"
    assert_absent 'image:.*:latest(["[:space:]]|$)' "$render" "latest image tags are forbidden in $render"
    assert_absent '^  name: [^[:space:]]*[A-Z]' "$render" "resource names must be lowercase DNS names in $render"
    assert_present '^kind: NetworkPolicy$' "$render" "network policies must render in $render"
    assert_present '^[[:space:]]+seccompProfile:$' "$render" "RuntimeDefault seccomp must render in $render"
    assert_present '^  FILE_SIZE_LIMIT: "5242880"$' "$render" "file-size limit must render as an exact decimal integer"
    assert_present '^  SIGNED_URL_EXPIRATION: "3600"$' "$render" "signed-URL expiration must render as an exact decimal integer"
    assert_present '^  HARD_DELETE_AFTER_DAYS: "60"$' "$render" "hard-delete retention must render as an exact decimal integer"
    assert_present '^  IMPORT_S3_BUCKET_NAME: "hangar-imports"$' "$render" "private import bucket must be configured"
    assert_absent '^[[:space:]]+(FILE_SIZE_LIMIT|SIGNED_URL_EXPIRATION|HARD_DELETE_AFTER_DAYS): "?[-+0-9.]+[eE][-+0-9]+' "$render" "integer application settings must not use exponent notation"
    redis_url_consumers="$(grep -Ec '^[[:space:]]+- name: REDIS_URL$' "$render")"
    expected_redis_consumers=5
    [[ "$render" != "$imports_render" ]] || expected_redis_consumers=6
    [[ "$redis_url_consumers" -eq "$expected_redis_consumers" ]] || fail "API, Live, workers, and migrator must each receive REDIS_URL in $render"
    api_probe_host_headers="$(grep -Ec '^[[:space:]]+- name: Host$' "$render")"
    [[ "$api_probe_host_headers" -eq 3 ]] || fail "every API HTTP probe must send the configured public host in $render"
    assert_present '^              deadline = time\.monotonic\(\) \+ 300$' "$render" "migrator must wait a bounded time for its database"
    assert_present '^              exec \./bin/docker-entrypoint-migrator\.sh$' "$render" "migrator entrypoint must run after its database wait"
done

assert_absent '^  name: hangar-hangar-import-worker$' "$production_render" "disabled imports must not render an import worker"
assert_present '^  name: hangar-hangar-import-worker$' "$imports_render" "enabled imports must render the dedicated worker"
assert_present '^[[:space:]]+value: imports$' "$imports_render" "the dedicated worker must consume only the imports queue"
assert_present '^  TODOIST_IMPORTS_ENABLED: "1"$' "$imports_render" "enabled imports must reach every application workload"
assert_present '^  TODOIST_IMPORT_MAX_ACTIVE_SOURCE_BYTES_PER_WORKSPACE: "10485760"$' "$imports_render" "import byte limits must render as exact decimal integers"
assert_present '^kind: PodDisruptionBudget$' "$imports_render" "the enabled multi-replica import worker must render a PDB"
assert_absent '^[[:space:]]+TODOIST_IMPORT_[A-Z_]+: "?[-+0-9.]+[eE][-+0-9]+' "$imports_render" "import integer settings must not use exponent notation"

assert_present '^  FILE_SIZE_LIMIT: "1073741824"$' "$boundary_render" "maximum file-size limit must render as an exact decimal integer"
assert_present '^  SIGNED_URL_EXPIRATION: "86400"$' "$boundary_render" "maximum signed-URL expiration must render as an exact decimal integer"
assert_present '^  HARD_DELETE_AFTER_DAYS: "3650"$' "$boundary_render" "maximum hard-delete retention must render as an exact decimal integer"
assert_absent '^[[:space:]]+(FILE_SIZE_LIMIT|SIGNED_URL_EXPIRATION|HARD_DELETE_AFTER_DAYS): "?[-+0-9.]+[eE][-+0-9]+' "$boundary_render" "maximum integer application settings must not use exponent notation"
assert_present '^  PDF_ASSET_ALLOWED_HOSTS: "storage.internal"$' "$boundary_render" "Live PDF asset hostname allowlist must render exactly"
live_secret_consumers="$(grep -Ec '^[[:space:]]+- name: LIVE_SERVER_SECRET_KEY$' "$production_render")"
[[ "$live_secret_consumers" -eq 2 ]] || fail "only Live and the general worker must receive LIVE_SERVER_SECRET_KEY"

assert_absent '^kind: Ingress$' "$gateway_render" "Gateway API mode must not render an NGINX Ingress"
assert_present '^kind: Gateway$' "$gateway_render" "Gateway API mode must render a Gateway when create is enabled"
gateway_route_count="$(grep -Ec '^kind: HTTPRoute$' "$gateway_render")"
[[ "$gateway_route_count" -eq 6 ]] || fail "Gateway API mode must render redirect, admin, spaces, live, API, and web routes"
for path in /god-mode /spaces /live /api; do
    assert_present "^[[:space:]]+value: ${path}$" "$gateway_render" "Gateway route is missing ${path}"
    assert_present "^[[:space:]]+replaceFullPath: ${path}/$" "$gateway_render" "Gateway route does not normalize ${path}"
done
assert_present '^[[:space:]]+value: /$' "$gateway_render" "Gateway route is missing the web root"
assert_present '^[[:space:]]+statusCode: 308$' "$gateway_render" "Gateway trailing-slash redirects must preserve the request method"
assert_present '^[[:space:]]+- name: X-Forwarded-Proto$' "$gateway_render" "Gateway API route must set X-Forwarded-Proto"
assert_present '^[[:space:]]+- name: X-Forwarded-Host$' "$gateway_render" "Gateway API route must set X-Forwarded-Host"
assert_present '^[[:space:]]+- name: X-Forwarded-Port$' "$gateway_render" "Gateway API route must set X-Forwarded-Port"
assert_present '^[[:space:]]+kubernetes\.io/metadata\.name: envoy-gateway-system$' "$gateway_render" "Envoy Gateway preset must select the data-plane namespace"
assert_present '^[[:space:]]+gateway\.envoyproxy\.io/owning-gateway-name: public-mtls$' "$gateway_render" "Envoy Gateway preset must select Pods owned by the configured Gateway"
assert_absent '^[[:space:]]+app\.kubernetes\.io/name: ingress-nginx$' "$gateway_render" "Envoy Gateway preset must not retain the NGINX Pod label"
evaluation_gateway_route_count="$(grep -Ec '^kind: HTTPRoute$' "$evaluation_gateway_render")"
[[ "$evaluation_gateway_route_count" -eq 7 ]] || fail "evaluation Gateway mode must add exactly one object-storage route"
assert_present '^  name: hangar-hangar-object-storage$' "$evaluation_gateway_render" "evaluation Gateway mode must render an object-storage HTTPRoute"
assert_present '^[[:space:]]+value: "/hangar"$' "$evaluation_gateway_render" "evaluation Gateway mode must route the presigned bucket path"
assert_present '^[[:space:]]+port: 8333$' "$evaluation_gateway_render" "evaluation Gateway mode must route to the S3 service port"
assert_present '^[[:space:]]+kubernetes\.io/metadata\.name: traefik$' "$traefik_render" "Traefik preset must select the conventional controller namespace"
assert_present '^[[:space:]]+app\.kubernetes\.io/name: traefik$' "$traefik_render" "Traefik preset must select Traefik Pods"
assert_absent '^[[:space:]]+app\.kubernetes\.io/name: ingress-nginx$' "$traefik_render" "Traefik preset must not retain the NGINX Pod label"
for variable in VITE_ADMIN_BASE_URL VITE_SPACE_BASE_URL VITE_LIVE_BASE_URL VITE_WEB_BASE_URL VITE_API_BASE_URL; do
    assert_present "^[[:space:]]+${variable}: \\\"https://hangar.example.com\\\",?$" "$production_render" "frontend runtime config is missing ${variable}"
done
assert_present '^[[:space:]]+VITE_LIVE_BASE_PATH: "/live",?$' "$production_render" "frontend runtime config is missing the Live base path"

assert_absent 'Source: hangar/charts/evaluation' "$production_render" "production must not render evaluation dependencies"
assert_present 'Source: hangar/charts/evaluation-postgresql' "$evaluation_render" "evaluation PostgreSQL did not render"
assert_present 'Source: hangar/charts/evaluation-rabbitmq' "$evaluation_render" "evaluation RabbitMQ did not render"
assert_present '^[[:space:]]+deprecated_features\.permit\.transient_nonexcl_queues = true$' "$evaluation_render" "evaluation RabbitMQ must permit the queue type required by Celery"
assert_present 'Source: hangar/charts/evaluation-valkey' "$evaluation_render" "evaluation Valkey did not render"
assert_present '^  name: hangar-hangar-evaluation-object-storage$' "$evaluation_render" "evaluation object storage did not render"
assert_present '^automountServiceAccountToken: false$' "$evaluation_render" "evaluation service accounts must disable token mounting"
dependency_service_account_uses="$(grep -Ec '^[[:space:]]+serviceAccountName: hangar-evaluation-dependencies$' "$evaluation_render")"
[[ "$dependency_service_account_uses" -eq 4 ]] || fail "every evaluation dependency Pod must use the tokenless dependency ServiceAccount"
assert_present 'AWS_S3_ENDPOINT_URL: "http://hangar-hangar-evaluation-object-storage:8333"' "$evaluation_render" "evaluation object storage endpoint is incorrect"
assert_present 'AWS_S3_PUBLIC_ENDPOINT_URL: "https://hangar-evaluation.example.com"' "$evaluation_render" "evaluation presigning must use the routed public origin"
assert_present 'AWS_S3_PUBLIC_ENDPOINT_URL: "https://s3.example.com"' "$production_render" "production presigning must use the public object-storage endpoint"
evaluation_object_storage_ingress_paths="$(grep -Ec '^[[:space:]]+- path: "/hangar"$' "$evaluation_render")"
[[ "$evaluation_object_storage_ingress_paths" -eq 1 ]] || fail "evaluation Ingress must route the presigned bucket path exactly once"
assert_absent '^[[:space:]]+- path: "/hangar-imports"$' "$evaluation_render" "private import bucket must not have a public Ingress route"
assert_absent '^[[:space:]]+value: /hangar-imports$' "$evaluation_gateway_render" "private import bucket must not have a public HTTPRoute"
assert_present '^  name: hangar-hangar-evaluation-object-storage-ingress$' "$evaluation_render" "evaluation object storage must allow ingress-controller traffic"
assert_absent '^[[:space:]]+- path: "/hangar"$' "$production_render" "production must not proxy object storage through the Hangar origin"
valkey_probe_auth_uses="$(grep -Ec '^[[:space:]]+- VALKEYCLI_AUTH="\$VALKEY_PASSWORD" valkey-cli --no-auth-warning --user hangar -h$' "$evaluation_render")"
valkey_probe_loopback_uses="$(grep -Ec '^[[:space:]]+127\.0\.0\.1 -p 6379 ping \| grep -qx PONG$' "$evaluation_render")"
[[ "$valkey_probe_auth_uses" -eq 3 && "$valkey_probe_loopback_uses" -eq 3 ]] || fail "every evaluation Valkey probe must authenticate over loopback"
assert_absent 'valkey-cli[^[:cntrl:]]*REDIS_URL' "$evaluation_render" "evaluation Valkey probes must not expose or route through REDIS_URL"
assert_absent '^kind: Secret$' "$evaluation_render" "charts must not generate credential Secrets"
assert_present '^  name: hangar-hangar-internal-api$' "$evaluation_render" "internal API network policy did not render"

assert_invalid "unknown deployment profile" --set-string deploymentProfile=invalid
assert_invalid "production with evaluation dependencies" --set evaluation.enabled=true
assert_invalid "evaluation without bundled dependencies" --set-string deploymentProfile=evaluation
assert_invalid "evaluation bucket colliding with the API route" \
    --set-string deploymentProfile=evaluation \
    --set evaluation.enabled=true \
    --set-string externalServices.objectStorage.bucket=api
assert_invalid "object-storage bucket containing a path separator" \
    --set-string externalServices.objectStorage.bucket=hangar/uploads
assert_invalid "import bucket containing a path separator" \
    --set-string externalServices.objectStorage.importBucket=hangar/imports
assert_invalid "HTTP production origin" --set-string publicUrl.scheme=http
assert_invalid "HTTP production object storage" --set-string externalServices.objectStorage.endpoint=http://s3.example.com
assert_invalid "HTTP production public object storage" --set-string externalServices.objectStorage.publicEndpoint=http://s3.example.com
assert_invalid "HTTP telemetry collector" --set-string observability.otlpEndpoint=http://otel.example.com
assert_invalid "PDF asset allowlist containing a URL" --set-string 'live.pdfAssetAllowedHosts[0]=http://storage.internal'
assert_invalid "disabled network policy" --set networkPolicy.enabled=false
assert_invalid "unknown ingress-controller preset" --set-string networkPolicy.ingressController.preset=unknown
assert_invalid "Gateway API with NGINX network-policy preset" --set gateway.enabled=true
assert_invalid "custom ingress-controller preset without selectors" --set-string networkPolicy.ingressController.preset=custom
assert_invalid "partial Envoy label override without selecting a preset" \
    --set-string 'networkPolicy.ingressController.podSelector.matchLabels.gateway\.envoyproxy\.io/owning-gateway-name=public-mtls'
assert_invalid "preset mixed with a custom selector" \
    --set-string networkPolicy.ingressController.preset=envoyGateway \
    --set-string networkPolicy.ingressController.podSelector.matchLabels.app=envoy
assert_invalid "multiple API replicas" --set api.replicas=2
assert_invalid "zero API workers" --set api.gunicornWorkers=0
assert_invalid "invalid Todoist preview rate" --set-string todoistImports.previewUserRate=unlimited
assert_invalid "zero Todoist active-user limit" --set todoistImports.maxActivePerUser=0
assert_invalid "excessive Todoist import worker concurrency" --set todoistImports.worker.concurrency=33
assert_invalid "multiple beat workers" --set beatWorker.replicas=2
assert_invalid "zero upload limit" --set application.fileSizeLimit=0
assert_invalid "short migrator database wait" --set migrator.databaseWaitSeconds=29
assert_invalid "migrator wait exceeding Job deadline" --set migrator.activeDeadlineSeconds=300 --set migrator.databaseWaitSeconds=300
assert_invalid "reserved Pod label override" --set-string global.podLabels.app\\.kubernetes\\.io/component=attacker
assert_invalid "mutable evaluation image" --set-string evaluation-postgresql.image.tag=18.4
assert_invalid "mutable evaluation object-storage image" --set-string evaluationObjectStorage.image.tag=4.39
assert_invalid "evaluation RBAC" --set evaluation-rabbitmq.rbac.create=true
assert_invalid "disabled RabbitMQ Celery compatibility" --set-string evaluation-rabbitmq.customConfig=
assert_invalid "evaluation service-account creation" --set evaluation-postgresql.serviceAccount.create=true
assert_invalid "unreviewed evaluation object-storage repository" --set-string evaluationObjectStorage.image.repository=example.invalid/object-store

helm package "$chart_dir" --dependency-update=false --destination "$tmp_dir" >/dev/null
echo "render-policy: production and evaluation renders passed"
