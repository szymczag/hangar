# Troubleshoot a Hangar Kubernetes installation

Use this guide to collect useful evidence without exposing credentials. Start at
the first failing layer and avoid changing multiple controls at once.

```bash
export RELEASE_NAME=hangar
export NAMESPACE=hangar-evaluation
```

## Safe initial checks

```bash
helm --namespace "$NAMESPACE" status "$RELEASE_NAME"
kubectl --namespace "$NAMESPACE" get \
  deployment,statefulset,pod,job,pvc,service,ingress,networkpolicy \
  --output wide
kubectl --namespace "$NAMESPACE" get events \
  --sort-by=.metadata.creationTimestamp
```

Describe only the failing resource:

```bash
kubectl --namespace "$NAMESPACE" describe pod POD_NAME
kubectl --namespace "$NAMESPACE" describe job JOB_NAME
```

Before sharing output, review environment variable names, URLs, annotations,
events, and logs for credentials or internal infrastructure details.

Never collect or share:

- `kubectl get secret ... --output yaml`;
- decoded Secret values;
- populated Secret manifests;
- Helm command lines that contain credentials;
- database, cache, queue, or object-storage URLs containing passwords; or
- TLS private keys and secret-manager logs.

## Symptom guide

| Symptom                              | Likely layer                                | First checks                                              |
| ------------------------------------ | ------------------------------------------- | --------------------------------------------------------- |
| `ImagePullBackOff` or `ErrImagePull` | Registry, architecture, or image reference  | Pod events, node architecture, anonymous digest pull      |
| `CreateContainerConfigError`         | Missing Secret or key                       | Pod events, Secret names and key names only               |
| Pod remains `Pending`                | Scheduling, resources, or PVC               | Pod events, AMD64 nodes, capacity, StorageClass           |
| PVC remains `Pending`                | CSI or StorageClass                         | PVC events, default/selected StorageClass, access mode    |
| Migration Job fails                  | Database, Secret, migration, or policy      | Job logs, database DNS/port, `DATABASE_URL` key presence  |
| Frontend returns 404/503             | Ingress class, route, Service, or readiness | Ingress events, endpoints, controller logs                |
| `/live` disconnects                  | WebSocket forwarding or Live readiness      | controller WebSocket settings, Live logs, endpoints       |
| Presigned upload returns 404/405     | Object-storage bucket route or backend      | rendered bucket path, storage Service, policy, proxy logs |
| Dependency timeout                   | DNS, NetworkPolicy, firewall, or TLS        | selectors, CIDRs, service endpoints, provider firewall    |
| Read-only filesystem error           | Application writes outside allowed paths    | Container log and image version; do not disable hardening |
| Upgrade rolled back                  | Migration or rollout failed                 | Helm history, revision Job, controller events             |

## Chart or image pull failures

Confirm the chart is public:

```bash
helm show chart oci://ghcr.io/szymczag/charts/hangar \
  --version 0.1.0-rc.43
```

Confirm the node architecture:

```bash
kubectl get nodes --label-columns kubernetes.io/arch
```

`0.1.0-rc.43` is AMD64-only. An ARM64-only cluster cannot schedule or run the
qualified images.

Published charts use digest references. Inspect the failed Pod's image without
printing its environment:

```bash
kubectl --namespace "$NAMESPACE" get pod POD_NAME \
  --output jsonpath='{range .spec.containers[*]}{.name}{"\t"}{.image}{"\n"}{end}'
```

If a private mirror is used, confirm the digest exists in the mirror and that
the configured pull Secret is present in the same namespace.

## Missing Secret or key

List Secret names:

```bash
kubectl --namespace "$NAMESPACE" get secret
```

List key names without values:

```bash
kubectl --namespace "$NAMESPACE" get secret SECRET_NAME \
  --output go-template='{{range $key, $value := .data}}{{$key}}{{"\n"}}{{end}}'
```

Compare the names with the [Secret interface](configuration.md#secret-interface).
After correcting a Secret, restart the affected Deployment; Secret-backed
environment variables do not update inside an existing process.

## Unschedulable Pods

Evaluation dependencies require AMD64 nodes. Check taints, allocatable resources,
and Pod requests:

```bash
kubectl get nodes --selector kubernetes.io/arch=amd64
kubectl describe node NODE_NAME
kubectl --namespace "$NAMESPACE" describe pod POD_NAME
```

Do not remove security contexts or dependency node selectors to force scheduling.
Add suitable capacity or choose a qualified cluster.

## Pending PVCs

```bash
kubectl --namespace "$NAMESPACE" describe pvc PVC_NAME
kubectl get storageclass
```

When there is no suitable default class, set all four evaluation storage-class
values. Do not set only one dependency and assume the others inherit it.

Retained PVCs from an earlier installation can also conflict with a new release
name, access mode, or ownership model. Do not delete them until their data and
recovery value are understood.

## Migration failures

Find the revision-scoped Job:

```bash
kubectl --namespace "$NAMESPACE" get job \
  --selector app.kubernetes.io/component=migrator
kubectl --namespace "$NAMESPACE" logs job/JOB_NAME
```

The migrator waits up to the configured `migrator.databaseWaitSeconds` for the
database host and port. A timeout usually indicates DNS, routing, NetworkPolicy,
firewall, TLS, credentials, or service availability—not a reason to increase the
timeout blindly.

Follow [failed migration recovery](operations.md#respond-to-a-failed-migration)
before retrying or rolling back.

## Ingress and WebSocket failures

```bash
kubectl --namespace "$NAMESPACE" describe ingress
kubectl --namespace "$NAMESPACE" get endpointslice \
  --selector app.kubernetes.io/instance="$RELEASE_NAME"
```

Confirm:

- DNS resolves to the active ingress endpoint;
- the IngressClass exists and the controller accepted the resource;
- the TLS Secret is in the release namespace and covers the public hostname;
- the ingress-controller namespace and Pod labels match the NetworkPolicy values;
- the controller forwards WebSocket upgrades for `/live`;
- request-body limits are at least `application.fileSizeLimit`; and
- forwarded host and scheme preserve the public HTTPS origin.

Controller logs are outside the Hangar namespace. Review them under your
cluster's access and redaction policy.

For evaluation uploads, confirm the rendered Ingress or HTTPRoute sends
`/<externalServices.objectStorage.bucket>` to the evaluation object-storage
Service on port `8333`. A `405` response from the web frontend means the bucket
path fell through to the `/` route. Also confirm the
`evaluation-object-storage-ingress` NetworkPolicy selects the actual ingress or
Gateway data-plane Pods. Presigned URLs and request cookies are credentials;
redact them from support output and invalidate them after accidental disclosure.

The import bucket must not appear in any Ingress or HTTPRoute. If an import is
rejected with `upload_failed`, verify that the configured import bucket differs
from the upload bucket and that an unsigned `HeadObject` request is denied. Do
not work around the check by adding a public route or bucket policy.

If the Imports page is absent or returns `404`, confirm
`todoistImports.enabled=true` in the effective Helm values and verify that API,
import-worker, and Beat rolled out from the same revision. Do not expose the
route by bypassing the feature gate. A Ready private bucket alone does not enable
the feature.

For jobs that remain queued, verify the dedicated `import-worker` exists and is
Ready, its `HANGAR_WORKER_QUEUE` is `imports`, RabbitMQ is reachable, and Beat is
running. General and mail workers intentionally do not consume import jobs. Do
not retarget imports to the general queue as an incident workaround.

An `import_quota_exceeded` response is a hard PostgreSQL admission denial. The
safe `limit` field identifies active user jobs, active workspace jobs, active
workspace source bytes, or workspace rows in the 24-hour window. A generic `429`
with a retry delay can instead be an API user/workspace throttle. Verify terminal
jobs released active reservations once and inspect append-only quota rejection
events; do not decrement ledger rows manually. Request counters are atomic across
API replicas. A Valkey failure returns `503` before upload parsing and must be
repaired rather than bypassed.

If an importer setting prevents startup, compare the effective values with the
[validated ranges](configuration.md#todoist-import-admission-and-worker). Rates
must use `<positive integer>/(second|minute|hour|day)`. Numeric values outside
the schema/runtime range are rejected rather than clamped.

## NetworkPolicy failures

Check whether the selected CNI enforces policy and whether DNS and ingress Pods
match the configured selectors:

```bash
kubectl get namespace --show-labels
kubectl get pods --all-namespaces --show-labels
kubectl --namespace "$NAMESPACE" get networkpolicy --output yaml
```

Review policy YAML before sharing it because private CIDRs reveal network
topology.

For private external services, confirm the resolved IP is covered by an exact
`networkPolicy.privateEgress` CIDR and port. FQDN changes are not tracked by
standard Kubernetes `NetworkPolicy`.

Do not disable `networkPolicy.enabled`; the schema and support contract require
it. Fix selectors, CIDRs, DNS, CNI enforcement, or provider firewalls instead.

## Read-only filesystem failures

All containers intentionally use a read-only root filesystem. A write failure
outside the declared temporary or data volumes is an application/image defect.
Record the container name, exact image digest, path, and redacted error. Do not
set `readOnlyRootFilesystem: false` or run the container as root.

## Build a redacted support bundle

Collect only non-secret control-plane metadata:

```bash
mkdir hangar-support

helm --namespace "$NAMESPACE" status "$RELEASE_NAME" \
  > hangar-support/helm-status.txt
kubectl --namespace "$NAMESPACE" get \
  deployment,statefulset,pod,job,pvc,service,ingress,networkpolicy \
  --output wide \
  > hangar-support/resources.txt
kubectl --namespace "$NAMESPACE" get events \
  --sort-by=.metadata.creationTimestamp \
  > hangar-support/events.txt
```

Add only the failing Pod or Job description and the smallest relevant log
window. Manually redact credentials, connection URLs, public/internal hostnames,
IP addresses, user data, tokens, cookies, and storage identifiers before sharing.

Record separately:

- chart version and OCI digest;
- Kubernetes, ingress-controller, CNI, and CSI versions;
- node architecture;
- deployment profile;
- the failing operation and timestamp; and
- exact reproduction steps.

Do not include `helm get values --all` without reviewing it: although the chart
contract excludes credentials from values, an operator may have added sensitive
custom annotations or unsupported values.
