#!/usr/bin/env bash

set -euo pipefail

readonly KIND_NODE_IMAGE="kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95"
readonly CILIUM_VERSION="1.19.5"
readonly CILIUM_CHART_DIGEST="sha256:557ea3b67b2380bdf91f3006ecea924e10e2963dbaf6085887652311e581460b"
readonly NGINX_CHART_VERSION="2.6.1"
readonly NGINX_CHART_DIGEST="sha256:fe6899d4087de3cdd809b5928b7373b0a97a58312f40733938dda84f4d571516"
readonly NGINX_IMAGE_DIGEST="sha256:0e23c34b1095aefb87d720d99a82528999cc93e53e74c0edd6339dba70d473bf"
readonly BUSYBOX_IMAGE="docker.io/busybox:stable@sha256:b7f3d86d6e84fc17718c48bcde1450807faa2d56704205c697b4bd5df7b9e29f"
readonly RELEASE_NAME="hangar"
readonly NAMESPACE="hangar-e2e"
readonly INGRESS_NAMESPACE="ingress-nginx"
readonly PUBLIC_HOST="hangar.test"

chart_reference="${1:-}"
if [[ -d "$chart_reference" && -f "$chart_reference/Chart.yaml" ]]; then
  chart_reference=$(cd "$chart_reference" && pwd)
elif [[ -f "$chart_reference" && "$chart_reference" == *.tgz ]]; then
  chart_reference="$(cd "$(dirname "$chart_reference")" && pwd)/$(basename "$chart_reference")"
else
  echo "usage: $0 CHART_DIRECTORY_OR_PACKAGE" >&2
  exit 2
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "the evaluation dependency qualification matrix currently requires an amd64 host" >&2
  exit 1
fi

for command in base64 curl docker helm kind kubectl openssl sha256sum; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "required command is unavailable: $command" >&2
    exit 1
  fi
done

chart_values=$(helm show values "$chart_reference")
if grep -Eq 'digest: sha256:0{64}$' <<<"$chart_values"; then
  echo "refusing to install a chart with fail-closed application image digests" >&2
  exit 1
fi

work_directory=$(mktemp -d)
cluster_name="hangar-e2e-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}-$$"
kubeconfig="$work_directory/kubeconfig"
export KUBECONFIG="$kubeconfig"

diagnostics() {
  local exit_code="$1"
  if ((exit_code == 0)); then
    return
  fi

  echo "::group::Hangar end-to-end diagnostics" >&2
  kubectl get nodes -o wide >&2 || true
  kubectl --namespace kube-system get pods -o wide >&2 || true
  kubectl --namespace "$INGRESS_NAMESPACE" get all -o wide >&2 || true
  kubectl --namespace "$NAMESPACE" get all,pvc,ingress,networkpolicy -o wide >&2 || true
  kubectl --namespace "$NAMESPACE" get events --sort-by=.lastTimestamp >&2 || true
  for pod in $(kubectl --namespace "$NAMESPACE" get pods -o name 2>/dev/null); do
    kubectl --namespace "$NAMESPACE" describe "$pod" >&2 || true
    kubectl --namespace "$NAMESPACE" logs "$pod" --all-containers --tail=200 >&2 || true
  done
  echo "::endgroup::" >&2
}

cleanup() {
  local exit_code=$?
  diagnostics "$exit_code"
  kind delete cluster --name "$cluster_name" >/dev/null 2>&1 || true
  rm -rf "$work_directory"
  exit "$exit_code"
}
trap cleanup EXIT

cat >"$work_directory/kind.yaml" <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  podSubnet: 10.244.0.0/16
  serviceSubnet: 10.96.0.0/16
nodes:
  - role: control-plane
    image: ${KIND_NODE_IMAGE}
    extraPortMappings:
      - containerPort: 30080
        hostPort: 8080
        listenAddress: 127.0.0.1
        protocol: TCP
      - containerPort: 30443
        hostPort: 8443
        listenAddress: 127.0.0.1
        protocol: TCP
EOF

kind create cluster \
  --name "$cluster_name" \
  --config "$work_directory/kind.yaml" \
  --kubeconfig "$kubeconfig"

cilium_pull_output=$(helm pull oci://quay.io/cilium/charts/cilium \
  --version "$CILIUM_VERSION" \
  --destination "$work_directory" 2>&1)
printf '%s\n' "$cilium_pull_output"
if ! grep -qFx "Digest: $CILIUM_CHART_DIGEST" <<<"$cilium_pull_output"; then
  echo "Cilium OCI chart digest did not match the qualification pin" >&2
  exit 1
fi
helm install cilium "$work_directory/cilium-${CILIUM_VERSION}.tgz" \
  --namespace kube-system \
  --set image.pullPolicy=IfNotPresent \
  --set ipam.mode=kubernetes \
  --set operator.replicas=1 \
  --wait \
  --timeout 10m
kubectl --namespace kube-system rollout status daemonset/cilium --timeout=5m
kubectl --namespace kube-system rollout status deployment/cilium-operator --timeout=5m
kubectl wait nodes --all --for=condition=Ready --timeout=5m

kubectl create namespace "$INGRESS_NAMESPACE"
kubectl label namespace "$INGRESS_NAMESPACE" \
  pod-security.kubernetes.io/enforce=privileged \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted

nginx_pull_output=$(helm pull oci://ghcr.io/nginx/charts/nginx-ingress \
  --version "$NGINX_CHART_VERSION" \
  --destination "$work_directory" 2>&1)
printf '%s\n' "$nginx_pull_output"
if ! grep -qFx "Digest: $NGINX_CHART_DIGEST" <<<"$nginx_pull_output"; then
  echo "NGINX OCI chart digest did not match the qualification pin" >&2
  exit 1
fi
helm install nginx-ingress "$work_directory/nginx-ingress-${NGINX_CHART_VERSION}.tgz" \
  --namespace "$INGRESS_NAMESPACE" \
  --skip-crds \
  --set controller.kind=daemonset \
  --set controller.image.tag=5.5.1 \
  --set controller.image.digest="$NGINX_IMAGE_DIGEST" \
  --set controller.enableCustomResources=false \
  --set controller.appprotect.enable=false \
  --set controller.appprotectdos.enable=false \
  --set controller.telemetryReporting.enable=false \
  --set controller.reportIngressStatus.enable=false \
  --set controller.service.type=NodePort \
  --set controller.service.httpPort.nodePort=30080 \
  --set controller.service.httpsPort.nodePort=30443 \
  --wait \
  --timeout 10m
nginx_daemonset=$(kubectl --namespace "$INGRESS_NAMESPACE" get daemonset \
  --selector app.kubernetes.io/name=nginx-ingress \
  -o jsonpath='{.items[0].metadata.name}')
kubectl --namespace "$INGRESS_NAMESPACE" rollout status \
  "daemonset/$nginx_daemonset" --timeout=5m
nginx_pods=$(kubectl --namespace "$INGRESS_NAMESPACE" get pods \
  --selector app.kubernetes.io/name=nginx-ingress \
  -o name)
if [[ "$nginx_pods" != pod/* ]]; then
  echo "NGINX ingress controller Pod was not found" >&2
  exit 1
fi

kubectl create namespace "$NAMESPACE"
kubectl label namespace "$NAMESPACE" \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted

docker exec "${cluster_name}-control-plane" sh -ec '
  for entry in postgresql:999 rabbitmq:999 valkey:999 object-storage:1000; do
    directory=${entry%:*}
    owner=${entry#*:}
    mkdir -p "/var/local/hangar-e2e/${directory}"
    chown "${owner}:${owner}" "/var/local/hangar-e2e/${directory}"
    chmod 0770 "/var/local/hangar-e2e/${directory}"
  done
'

cat >"$work_directory/storage.yaml" <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: kind-static-postgresql
provisioner: kubernetes.io/no-provisioner
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: kind-static-rabbitmq
provisioner: kubernetes.io/no-provisioner
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: kind-static-valkey
provisioner: kubernetes.io/no-provisioner
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: kind-static-object-storage
provisioner: kubernetes.io/no-provisioner
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ${cluster_name}-postgresql
spec:
  capacity:
    storage: 20Gi
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: kind-static-postgresql
  hostPath:
    path: /var/local/hangar-e2e/postgresql
    type: DirectoryOrCreate
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ${cluster_name}-rabbitmq
spec:
  capacity:
    storage: 20Gi
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: kind-static-rabbitmq
  hostPath:
    path: /var/local/hangar-e2e/rabbitmq
    type: DirectoryOrCreate
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ${cluster_name}-valkey
spec:
  capacity:
    storage: 20Gi
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: kind-static-valkey
  hostPath:
    path: /var/local/hangar-e2e/valkey
    type: DirectoryOrCreate
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ${cluster_name}-object-storage
spec:
  capacity:
    storage: 20Gi
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: kind-static-object-storage
  hostPath:
    path: /var/local/hangar-e2e/object-storage
    type: DirectoryOrCreate
EOF
kubectl apply --filename "$work_directory/storage.yaml"

application_secret=$(openssl rand -hex 32)
live_secret=$(openssl rand -hex 32)
database_superuser_password=$(openssl rand -hex 24)
database_password=$(openssl rand -hex 24)
cache_password=$(openssl rand -hex 24)
queue_password=$(openssl rand -hex 24)
erlang_cookie=$(openssl rand -hex 32)
object_access_key=$(openssl rand -hex 12)
object_secret_key=$(openssl rand -hex 32)

umask 077
cat >"$work_directory/secrets.yaml" <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: hangar-application
  namespace: ${NAMESPACE}
type: Opaque
stringData:
  SECRET_KEY: ${application_secret}
---
apiVersion: v1
kind: Secret
metadata:
  name: hangar-live
  namespace: ${NAMESPACE}
type: Opaque
stringData:
  LIVE_SERVER_SECRET_KEY: ${live_secret}
---
apiVersion: v1
kind: Secret
metadata:
  name: hangar-database
  namespace: ${NAMESPACE}
type: Opaque
stringData:
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: ${database_superuser_password}
  POSTGRES_DB: hangar
  USERDB_USER: hangar
  USERDB_PASSWORD: ${database_password}
  DATABASE_URL: postgresql://hangar:${database_password}@hangar-evaluation-postgresql:5432/hangar
---
apiVersion: v1
kind: Secret
metadata:
  name: hangar-cache
  namespace: ${NAMESPACE}
type: Opaque
stringData:
  REDIS_URL: redis://hangar:${cache_password}@hangar-evaluation-valkey:6379/0
  VALKEY_PASSWORD: ${cache_password}
  users.acl: "user default off\\nuser hangar on >${cache_password} ~* &* +@all\\n"
---
apiVersion: v1
kind: Secret
metadata:
  name: hangar-queue
  namespace: ${NAMESPACE}
type: Opaque
stringData:
  RABBITMQ_DEFAULT_USER: hangar
  RABBITMQ_DEFAULT_PASS: ${queue_password}
  ERLANG_COOKIE: ${erlang_cookie}
  AMQP_URL: amqp://hangar:${queue_password}@hangar-evaluation-rabbitmq:5672/
---
apiVersion: v1
kind: Secret
metadata:
  name: hangar-object-storage
  namespace: ${NAMESPACE}
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: ${object_access_key}
  AWS_SECRET_ACCESS_KEY: ${object_secret_key}
EOF
kubectl apply --filename "$work_directory/secrets.yaml"
unset application_secret live_secret database_superuser_password database_password
unset cache_password queue_password erlang_cookie object_access_key object_secret_key

openssl req -x509 -newkey rsa:2048 -sha256 -days 1 -nodes \
  -keyout "$work_directory/tls.key" \
  -out "$work_directory/tls.crt" \
  -subj "/CN=${PUBLIC_HOST}" \
  -addext "subjectAltName=DNS:${PUBLIC_HOST}" >/dev/null 2>&1
kubectl --namespace "$NAMESPACE" create secret tls hangar-tls \
  --cert "$work_directory/tls.crt" \
  --key "$work_directory/tls.key"

registry_values=""
if [[ -n "${REGISTRY_PASSWORD:-}" ]]; then
  if [[ -z "${REGISTRY_USERNAME:-}" ]]; then
    echo "REGISTRY_USERNAME is required when REGISTRY_PASSWORD is set" >&2
    exit 1
  fi
  registry_auth=$(printf '%s:%s' "$REGISTRY_USERNAME" "$REGISTRY_PASSWORD" | base64 | tr -d '\n')
  cat >"$work_directory/registry.json" <<EOF
{"auths":{"ghcr.io":{"auth":"${registry_auth}"}}}
EOF
  kubectl --namespace "$NAMESPACE" create secret generic hangar-registry \
    --type=kubernetes.io/dockerconfigjson \
    --from-file=.dockerconfigjson="$work_directory/registry.json"
  unset registry_auth REGISTRY_PASSWORD
  registry_values=$'global:\n  imagePullSecrets:\n    - name: hangar-registry'
fi

cat >"$work_directory/values.yaml" <<EOF
deploymentProfile: evaluation
publicUrl:
  scheme: https
  host: ${PUBLIC_HOST}
evaluation:
  enabled: true
ingress:
  className: nginx
  annotations:
    nginx.org/ssl-redirect: "true"
    nginx.org/websocket-services: hangar-hangar-live
  tls:
    secretName: hangar-tls
networkPolicy:
  ingressController:
    namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: ${INGRESS_NAMESPACE}
    podSelector:
      matchLabels:
        app.kubernetes.io/name: nginx-ingress
web:
  replicas: 1
  pdb:
    enabled: false
admin:
  replicas: 1
  pdb:
    enabled: false
space:
  replicas: 1
  pdb:
    enabled: false
live:
  replicas: 1
  pdb:
    enabled: false
evaluation-postgresql:
  storage:
    className: kind-static-postgresql
evaluation-rabbitmq:
  storage:
    className: kind-static-rabbitmq
evaluation-valkey:
  storage:
    className: kind-static-valkey
evaluationObjectStorage:
  persistence:
    storageClass: kind-static-object-storage
${registry_values}
EOF

helm upgrade --install "$RELEASE_NAME" "$chart_reference" \
  --namespace "$NAMESPACE" \
  --values "$work_directory/values.yaml" \
  --wait \
  --wait-for-jobs \
  --timeout 20m

for workload in \
  deployment/hangar-hangar-admin \
  deployment/hangar-hangar-api \
  deployment/hangar-hangar-beat-worker \
  deployment/hangar-hangar-live \
  deployment/hangar-hangar-space \
  deployment/hangar-hangar-web \
  deployment/hangar-hangar-worker \
  statefulset/hangar-evaluation-postgresql \
  statefulset/hangar-evaluation-rabbitmq \
  statefulset/hangar-evaluation-valkey \
  statefulset/hangar-hangar-evaluation-object-storage; do
  kubectl --namespace "$NAMESPACE" rollout status "$workload" --timeout=5m
done
pvc_phases=$(kubectl --namespace "$NAMESPACE" get pvc \
  -o jsonpath='{range .items[*]}{.status.phase}{"\n"}{end}')
if grep -qv '^Bound$' <<<"$pvc_phases"; then
  echo "not all evaluation PVCs are Bound" >&2
  exit 1
fi
migration_1_succeeded=$(kubectl --namespace "$NAMESPACE" get job hangar-hangar-migrate-1 \
  -o jsonpath='{.status.succeeded}')
if [[ "$migration_1_succeeded" != "1" ]]; then
  echo "initial migration Job did not succeed exactly once" >&2
  exit 1
fi

curl --noproxy '*' --fail --silent --show-error --cacert "$work_directory/tls.crt" \
  --resolve "${PUBLIC_HOST}:8443:127.0.0.1" \
  "https://${PUBLIC_HOST}:8443/" >/dev/null
curl --noproxy '*' --fail --silent --show-error --cacert "$work_directory/tls.crt" \
  --resolve "${PUBLIC_HOST}:8443:127.0.0.1" \
  "https://${PUBLIC_HOST}:8443/god-mode/" >/dev/null
curl --noproxy '*' --fail --silent --show-error --cacert "$work_directory/tls.crt" \
  --resolve "${PUBLIC_HOST}:8443:127.0.0.1" \
  "https://${PUBLIC_HOST}:8443/spaces/" >/dev/null
live_health=$(curl --noproxy '*' --fail --silent --show-error --cacert "$work_directory/tls.crt" \
  --resolve "${PUBLIC_HOST}:8443:127.0.0.1" \
  "https://${PUBLIC_HOST}:8443/live/health/")
if [[ "$live_health" != *'"status":"OK"'* ]]; then
  echo "Live health response did not report OK" >&2
  exit 1
fi

api_status=$(curl --noproxy '*' --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --cacert "$work_directory/tls.crt" \
  --resolve "${PUBLIC_HOST}:8443:127.0.0.1" \
  "https://${PUBLIC_HOST}:8443/api/instances/")
if ((api_status >= 500)); then
  echo "API ingress returned HTTP $api_status" >&2
  exit 1
fi

redirect_headers="$work_directory/http-redirect-headers"
redirect_status=$(curl --noproxy '*' --silent --show-error --head \
  --output /dev/null \
  --dump-header "$redirect_headers" \
  --write-out '%{http_code}' \
  --resolve "${PUBLIC_HOST}:8080:127.0.0.1" \
  --header "Host: ${PUBLIC_HOST}" \
  "http://${PUBLIC_HOST}:8080/")
redirect_location=$(awk 'tolower($1) == "location:" { sub(/\r$/, "", $2); location = $2 } END { print location }' "$redirect_headers")
redirect_host_regex="${PUBLIC_HOST//./\\.}"
if [[ ! "$redirect_status" =~ ^30(1|2|7|8)$ ]] || \
  [[ ! "$redirect_location" =~ ^https://${redirect_host_regex}(:[0-9]+)?(/|$) ]]; then
  echo "expected same-host HTTPS redirect, got HTTP $redirect_status location '$redirect_location'" >&2
  exit 1
fi

set +e
curl --noproxy '*' --fail --silent --show-error --http1.1 --max-time 5 \
  --cacert "$work_directory/tls.crt" \
  --resolve "${PUBLIC_HOST}:8443:127.0.0.1" \
  --header 'Connection: Upgrade' \
  --header 'Upgrade: websocket' \
  --header 'Sec-WebSocket-Version: 13' \
  --header 'Sec-WebSocket-Key: SGFuZ2FyRTJFVGVzdEtleQ==' \
  --dump-header "$work_directory/websocket-headers" \
  "https://${PUBLIC_HOST}:8443/live/collaboration/" >/dev/null
websocket_curl_status=$?
set -e
if [[ "$websocket_curl_status" -ne 0 && "$websocket_curl_status" -ne 28 ]]; then
  echo "WebSocket probe failed with curl status $websocket_curl_status" >&2
  exit 1
fi
if ! grep -E '^HTTP/1\.1 101 ' "$work_directory/websocket-headers" >/dev/null; then
  echo "WebSocket probe did not receive HTTP 101 Switching Protocols" >&2
  exit 1
fi

api_service_ip=$(kubectl --namespace "$NAMESPACE" get service hangar-hangar-api -o jsonpath='{.spec.clusterIP}')
cat >"$work_directory/network-probes.yaml" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: allowed-dependencies
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/instance: ${RELEASE_NAME}
    app.kubernetes.io/component: worker
spec:
  automountServiceAccountToken: false
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 65534
    runAsGroup: 65534
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: ${BUSYBOX_IMAGE}
      command: [sh, -ec]
      args:
        - >-
          nc -z -w 5 hangar-evaluation-postgresql 5432 &&
          nc -z -w 5 hangar-evaluation-rabbitmq 5672 &&
          nc -z -w 5 hangar-evaluation-valkey 6379 &&
          nc -z -w 5 hangar-hangar-evaluation-object-storage 8333
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
---
apiVersion: v1
kind: Pod
metadata:
  name: allowed-api
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/instance: ${RELEASE_NAME}
    app.kubernetes.io/component: live
spec:
  automountServiceAccountToken: false
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 65534
    runAsGroup: 65534
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: ${BUSYBOX_IMAGE}
      command: [sh, -ec]
      args: ["nc -z -w 5 hangar-hangar-api 8000"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
---
apiVersion: v1
kind: Pod
metadata:
  name: denied-api
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/instance: ${RELEASE_NAME}
    app.kubernetes.io/component: web
spec:
  automountServiceAccountToken: false
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 65534
    runAsGroup: 65534
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: ${BUSYBOX_IMAGE}
      command: [sh, -ec]
      args: ["! nc -z -w 5 ${api_service_ip} 8000"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
---
apiVersion: v1
kind: Pod
metadata:
  name: denied-metadata
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/instance: ${RELEASE_NAME}
    app.kubernetes.io/component: worker
spec:
  automountServiceAccountToken: false
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 65534
    runAsGroup: 65534
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: ${BUSYBOX_IMAGE}
      command: [sh, -ec]
      args: ["! nc -z -w 5 169.254.169.254 80"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
EOF
kubectl apply --filename "$work_directory/network-probes.yaml"
for probe in allowed-dependencies allowed-api denied-api denied-metadata; do
  kubectl --namespace "$NAMESPACE" wait pod/$probe \
    --for=jsonpath='{.status.phase}'=Succeeded \
    --timeout=2m
done

object_storage_pod=$(kubectl --namespace "$NAMESPACE" get pod \
  --selector app.kubernetes.io/name=evaluationObjectStorage \
  -o jsonpath='{.items[0].metadata.name}')
kubectl --namespace "$NAMESPACE" exec "$object_storage_pod" -- \
  sh -ec 'printf hangar-e2e > /data/hangar-e2e-marker'
kubectl --namespace "$NAMESPACE" delete pod "$object_storage_pod" --wait=true
kubectl --namespace "$NAMESPACE" rollout status statefulset/hangar-hangar-evaluation-object-storage --timeout=5m
replacement_object_storage_pod=$(kubectl --namespace "$NAMESPACE" get pod \
  --selector app.kubernetes.io/name=evaluationObjectStorage \
  -o jsonpath='{.items[0].metadata.name}')
kubectl --namespace "$NAMESPACE" exec "$replacement_object_storage_pod" -- \
  grep -qx hangar-e2e /data/hangar-e2e-marker

helm upgrade "$RELEASE_NAME" "$chart_reference" \
  --namespace "$NAMESPACE" \
  --values "$work_directory/values.yaml" \
  --set application.signedUrlExpiration=7200 \
  --rollback-on-failure \
  --wait \
  --wait-for-jobs \
  --timeout 20m
migration_2_succeeded=$(kubectl --namespace "$NAMESPACE" get job hangar-hangar-migrate-2 \
  -o jsonpath='{.status.succeeded}')
if [[ "$migration_2_succeeded" != "1" ]]; then
  echo "upgrade migration Job did not succeed exactly once" >&2
  exit 1
fi
release_status=$(helm --namespace "$NAMESPACE" status "$RELEASE_NAME")
if ! grep -q '^STATUS: deployed$' <<<"$release_status"; then
  echo "Helm release is not deployed after upgrade" >&2
  exit 1
fi
upgraded_live_health=$(curl --noproxy '*' --fail --silent --show-error --cacert "$work_directory/tls.crt" \
  --resolve "${PUBLIC_HOST}:8443:127.0.0.1" \
  "https://${PUBLIC_HOST}:8443/live/health/")
if [[ "$upgraded_live_health" != *'"status":"OK"'* ]]; then
  echo "Live health response did not report OK after upgrade" >&2
  exit 1
fi

helm --namespace "$NAMESPACE" uninstall "$RELEASE_NAME" --wait --timeout 10m
retained_pvc_count=$(kubectl --namespace "$NAMESPACE" get pvc --no-headers | wc -l | tr -d ' ')
if [[ "$retained_pvc_count" -ne 4 ]]; then
  echo "expected 4 retained evaluation PVCs, found $retained_pvc_count" >&2
  exit 1
fi

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat >>"$GITHUB_STEP_SUMMARY" <<'EOF'
## Helm end-to-end qualification

- Kubernetes 1.35.5 on Kind 0.32.0
- Cilium 1.19.5 policy enforcement
- F5 NGINX Ingress Controller 5.5.1
- Exact packaged chart installed with immutable application image digests
- Restricted Pod Security, TLS ingress, WebSocket upgrade, and HTTP redirect passed
- Dependency/API allow rules and API/link-local deny rules passed
- Object-storage pod recreation, Helm upgrade, migration, and PVC-retaining uninstall passed
EOF
fi

echo "Hangar Helm end-to-end qualification passed on Kubernetes 1.35.5"
