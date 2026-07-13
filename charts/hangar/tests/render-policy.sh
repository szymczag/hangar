#!/usr/bin/env bash

set -euo pipefail

chart_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

production_render="$tmp_dir/production.yaml"
evaluation_render="$tmp_dir/evaluation.yaml"
kube_version="${KUBE_VERSION:-1.35.0}"

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

helm lint "$chart_dir" --kube-version "$kube_version"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" >"$production_render"
helm template hangar "$chart_dir" --namespace hangar --kube-version "$kube_version" \
    --values "$chart_dir/ci/evaluation-values.yaml" >"$evaluation_render"

for render in "$production_render" "$evaluation_render"; do
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
done

assert_absent 'Source: hangar/charts/evaluation' "$production_render" "production must not render evaluation dependencies"
assert_present 'Source: hangar/charts/evaluation-postgresql' "$evaluation_render" "evaluation PostgreSQL did not render"
assert_present 'Source: hangar/charts/evaluation-rabbitmq' "$evaluation_render" "evaluation RabbitMQ did not render"
assert_present 'Source: hangar/charts/evaluation-valkey' "$evaluation_render" "evaluation Valkey did not render"
assert_present '^  name: hangar-hangar-evaluation-object-storage$' "$evaluation_render" "evaluation object storage did not render"
assert_present '^automountServiceAccountToken: false$' "$evaluation_render" "evaluation service accounts must disable token mounting"
dependency_service_account_uses="$(grep -Ec '^[[:space:]]+serviceAccountName: hangar-evaluation-dependencies$' "$evaluation_render")"
[[ "$dependency_service_account_uses" -eq 4 ]] || fail "every evaluation dependency Pod must use the tokenless dependency ServiceAccount"
assert_present 'AWS_S3_ENDPOINT_URL: "http://hangar-hangar-evaluation-object-storage:8333"' "$evaluation_render" "evaluation object storage endpoint is incorrect"
assert_absent '^kind: Secret$' "$evaluation_render" "charts must not generate credential Secrets"
assert_present '^  name: hangar-hangar-internal-api$' "$evaluation_render" "internal API network policy did not render"

assert_invalid "unknown deployment profile" --set-string deploymentProfile=invalid
assert_invalid "production with evaluation dependencies" --set evaluation.enabled=true
assert_invalid "evaluation without bundled dependencies" --set-string deploymentProfile=evaluation
assert_invalid "HTTP production origin" --set-string publicUrl.scheme=http
assert_invalid "HTTP production object storage" --set-string externalServices.objectStorage.endpoint=http://s3.example.com
assert_invalid "HTTP telemetry collector" --set-string observability.otlpEndpoint=http://otel.example.com
assert_invalid "disabled network policy" --set networkPolicy.enabled=false
assert_invalid "multiple API replicas" --set api.replicas=2
assert_invalid "zero API workers" --set api.gunicornWorkers=0
assert_invalid "multiple beat workers" --set beatWorker.replicas=2
assert_invalid "zero upload limit" --set application.fileSizeLimit=0
assert_invalid "reserved Pod label override" --set-string global.podLabels.app\\.kubernetes\\.io/component=attacker
assert_invalid "mutable evaluation image" --set-string evaluation-postgresql.image.tag=18.4
assert_invalid "mutable evaluation object-storage image" --set-string evaluationObjectStorage.image.tag=4.39
assert_invalid "evaluation RBAC" --set evaluation-rabbitmq.rbac.create=true
assert_invalid "evaluation service-account creation" --set evaluation-postgresql.serviceAccount.create=true
assert_invalid "unreviewed evaluation object-storage repository" --set-string evaluationObjectStorage.image.repository=example.invalid/object-store

helm package "$chart_dir" --dependency-update=false --destination "$tmp_dir" >/dev/null
echo "render-policy: production and evaluation renders passed"
