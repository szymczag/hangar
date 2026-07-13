# Hangar Helm chart

This chart deploys Hangar with secure Kubernetes defaults and two explicit
profiles:

- `production` uses external PostgreSQL, Valkey, RabbitMQ, and S3-compatible
  storage. This is the durable deployment model.
- `evaluation` bundles persistent, single-replica dependencies for non-critical
  testing. It is not a high-availability or production recommendation.

The chart is release-candidate software until the qualification checklist in
`docs/kubernetes-deployment-plan.md` is complete.

## Prerequisites

- Kubernetes 1.30 through 1.35; CI validates rendered resources against 1.35.
- Helm 4.2 for the qualified client path.
- A default `StorageClass`, or explicit storage-class overrides for evaluation.
- An ingress controller and a TLS Secret in the release namespace.
- A CNI that enforces `NetworkPolicy`.
- Pre-existing Kubernetes Secrets. The chart never generates application or
  dependency credentials.

Published charts contain release image digests. The source chart deliberately
uses all-zero application digests as fail-closed placeholders; do not install a
package built directly from an unqualified source checkout.

Use `global.imagePullSecrets` for a registry credential shared by all application
images, or a component's `image.pullSecrets` for a narrower credential. The
worker, beat worker, and migrator use `api.image.pullSecrets` because they run the
API image.

In the commands below, `VERSION` is the chart SemVer without the product's `v`
prefix, for example `0.1.0-rc.1`.

## Install the production profile

1. Provision and back up compatible PostgreSQL, Valkey, RabbitMQ, and
   S3-compatible services. Require TLS and authentication at their service
   boundaries.
2. Create the Secrets listed below in the target namespace through your secret
   manager, such as External Secrets, SOPS, or Sealed Secrets.
3. Copy `examples/production-values.yaml` outside the repository and set the
   hostname, ingress class, object-storage endpoint, and private egress rules.
4. Render and review the exact release before installing it.

```bash
helm template hangar oci://ghcr.io/szymczag/charts/hangar \
  --version VERSION \
  --namespace hangar \
  --values production-values.yaml > rendered.yaml
```

5. Install atomically and wait for the revision-scoped migration Job.

```bash
helm upgrade --install hangar oci://ghcr.io/szymczag/charts/hangar \
  --version VERSION \
  --namespace hangar \
  --create-namespace \
  --values production-values.yaml \
  --atomic \
  --wait \
  --wait-for-jobs \
  --timeout 15m
```

### Required production Secrets

| Secret                  | Required keys                                | Consumer               |
| ----------------------- | -------------------------------------------- | ---------------------- |
| `hangar-application`    | `SECRET_KEY`                                 | API, workers, migrator |
| `hangar-live`           | `LIVE_SERVER_SECRET_KEY`                     | Live service           |
| `hangar-database`       | `DATABASE_URL`                               | API, workers, migrator |
| `hangar-cache`          | `REDIS_URL`                                  | API, Live, workers     |
| `hangar-queue`          | `AMQP_URL`                                   | API and Celery workers |
| `hangar-object-storage` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | API and task worker    |

Use application-specific database, cache, queue, and bucket identities. Do not
use provider administrator credentials. Encode reserved URL characters in the
connection URLs.

### Rotate a Secret

The chart references existing Secrets and intentionally does not copy their
contents into the Helm release. Updating a Secret does not automatically restart
its consumers.

1. Follow the dependency's overlap procedure first when a credential can support
   old and new values concurrently.
2. Update the managed Secret without printing its value to CI or shell history.
3. Restart only the consumers listed in the table above. For the API image, this
   can include the API and task worker; cache or queue rotation can also require
   Live or beat.
4. Wait for rollout and application health, then revoke the old credential.
5. Confirm logs and events contain no credential values.

For an application `SECRET_KEY` change, invalidate existing sessions and test
signed links explicitly. Treat database or object-storage rotation as a
coordinated maintenance operation when overlap is unavailable.

Private RFC1918, carrier-grade NAT, loopback, link-local, and cluster ranges are
denied by default. Add the smallest destination CIDRs and ports under
`networkPolicy.privateEgress` for private external services.

## Install the evaluation profile

Evaluation is suitable for a disposable lab or compatibility test. It retains
PVCs, but it does not provide dependency high availability or a supported
in-place major-version upgrade path.

1. Use a dedicated namespace with Pod Security Admission set to `restricted`.
2. Copy `examples/evaluation-secrets.example.yaml` outside the repository.
   Replace every `CHANGE_ME` value and place the populated manifest under secret
   management. The example assumes release name `hangar`; update its internal
   service names if you choose another release name.
3. Apply the managed Secret resources and install with the evaluation values.

```bash
kubectl create namespace hangar-evaluation
kubectl label namespace hangar-evaluation \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted

helm upgrade --install hangar oci://ghcr.io/szymczag/charts/hangar \
  --version VERSION \
  --namespace hangar-evaluation \
  --values evaluation-values.yaml \
  --atomic \
  --wait \
  --wait-for-jobs \
  --timeout 20m
```

Start `evaluation-values.yaml` with:

```yaml
deploymentProfile: evaluation

publicUrl:
  scheme: https
  host: hangar-evaluation.example.com

evaluation:
  enabled: true

ingress:
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
  tls:
    secretName: hangar-tls
```

The evaluation dependency images are pinned to amd64 platform digests, so the
profile schedules them only on `kubernetes.io/arch=amd64` nodes. See
`DEPENDENCIES.md` for the exact chart and image evidence.

To use a non-default storage class, set all four values explicitly:

```yaml
evaluation-postgresql:
  storage:
    className: encrypted-rwo
evaluation-rabbitmq:
  storage:
    className: encrypted-rwo
evaluation-valkey:
  storage:
    className: encrypted-rwo
evaluationObjectStorage:
  persistence:
    storageClass: encrypted-rwo
```

## Verify an installation

The migration Job name includes the Helm revision. Verify that it completed and
that all workloads became ready:

```bash
kubectl --namespace hangar get jobs,pods,pvc,ingress,networkpolicy
kubectl --namespace hangar rollout status deployment/hangar-hangar-api --timeout=5m
kubectl --namespace hangar logs job/hangar-hangar-migrate-REVISION
```

Then verify the public origin, `/api`, `/live`, `/god-mode`, and `/spaces` through
the ingress. Confirm plain HTTP redirects to HTTPS, forwarded scheme and host are
correct, and direct access to internal Services is unavailable. Test an upload
and download before admitting users.

## Verify release artifacts

Release tags use the namespaced form `hangar-vX.Y.Z`; chart versions omit both
`hangar-` and `v`. Download `chart-oci-digest.txt`, `image-digests.txt`, the
chart archive, and its `.sha256` file from the corresponding GitHub Release.

```bash
sha256sum --check hangar-VERSION.tgz.sha256
gh attestation verify hangar-VERSION.tgz --repo szymczag/hangar

CHART_REF="$(cat chart-oci-digest.txt)"
IDENTITY="https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/hangar-vVERSION"
cosign verify \
  --certificate-identity "$IDENTITY" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  "$CHART_REF"
```

Apply the same Cosign command to every digest reference in
`image-digests.txt`. Verification must target the digest, expected workflow
identity, namespaced release tag, and GitHub OIDC issuer; verifying only a
mutable tag is insufficient.

## Upgrade and roll back

Before every upgrade:

1. Back up PostgreSQL and uploaded objects at a coordinated recovery point.
2. Render the new chart with the production values and review the manifest diff.
3. Read application and dependency release notes, especially before any database
   major-version change.
4. Verify the new chart and image attestations and digests.

Use the same atomic command as installation with a new chart version. The
migrator is a normal, revision-scoped Job with bounded retries and a 15-minute
deadline.

`helm rollback` restores Kubernetes resources, but it cannot reverse a database
migration. Roll back only when the application release declares the schema
backward-compatible. Otherwise restore the coordinated backup into a clean
environment and deploy the matching chart version.

### Backup and restore

The chart does not orchestrate application-consistent backups. Production
operators must use service-native backup tooling and record a common recovery
point for PostgreSQL and uploaded objects. A release is not qualified until a
restore into a clean namespace proves authentication, representative projects,
uploads, background jobs, and object downloads.

For evaluation, snapshot the PostgreSQL and object-storage PVCs only with a CSI
driver and storage backend whose consistency behavior has been tested. Copying
live volume files is not a supported backup method. Retained PVCs protect against
accidental uninstall; they are not a backup.

## Uninstall and data retention

```bash
helm uninstall hangar --namespace hangar
```

Production data lives in external services and is unaffected. Evaluation PVCs
are intentionally retained where supported. Inventory and delete them only after
confirming that their data is no longer required:

```bash
kubectl --namespace hangar get pvc
```

## Security behavior

- Application and evaluation images use immutable digest references.
- Containers run as non-root with a read-only root filesystem, all Linux
  capabilities dropped, privilege escalation disabled, and `RuntimeDefault`
  seccomp.
- Service-account token automounting is disabled and the chart creates no RBAC.
- Default-deny ingress and egress policies cover every release pod.
- Only ingress-controller traffic reaches public workloads. Dependency services
  remain cluster-internal.
- Public egress is limited to TCP 443. Private destinations require explicit
  CIDR and port rules.
- Telemetry and release discovery are disabled by default in the application
  configuration.
- Secret values are referenced from existing Secrets and are never stored in a
  ConfigMap or generated by Helm.

NetworkPolicy enforcement does not replace a firewall, service-side TLS, or
cloud security groups. Confirm effective traffic with the CNI used by each
qualified Kubernetes distribution.

Telemetry export requires two deliberate actions: configure an explicit HTTPS
collector under `observability.otlpEndpoint`, and opt the instance in through
the application. Leaving either control unset sends nothing. Hangar does not
fall back to a Plane or other third-party collector.

## Operational constraints

- API replicas are fixed at one until startup registration, bucket creation,
  cache clearing, and static collection are moved out of the web process.
- Exactly one beat worker is supported; the chart has no scheduler leader
  election.
- The evaluation dependencies are single replica and must not be presented as
  highly available.
- The chart does not install cert-manager, an ingress controller, a CSI driver,
  a CNI, an external secret operator, or observability infrastructure.

## Validate a source checkout

Dependencies are vendored and locked so validation does not silently select new
charts.

```bash
charts/hangar/scripts/verify-dependencies.sh
charts/hangar/tests/render-policy.sh
```

CI also runs kubeconform against Kubernetes 1.35 schemas, kube-linter security
and reliability checks, negative schema tests, and package generation.

Maintainers can run the live evaluation qualification against a staged release
chart on an AMD64 Docker host. The source chart cannot be used directly because
its application digests intentionally fail closed. Stage it with
`scripts/prepare-release.sh`, install the pinned clients, and then run:

```bash
charts/hangar/tests/install-e2e-tools.sh /tmp/hangar-e2e-bin
PATH="/tmp/hangar-e2e-bin:$PATH" \
  charts/hangar/tests/e2e-kind.sh /path/to/staged/hangar-chart
```

If GHCR requires authentication, set `REGISTRY_USERNAME` and
`REGISTRY_PASSWORD`; the harness creates a namespace-local pull Secret and does
not print the credential. It generates all application credentials and TLS
material in a restricted temporary directory and deletes the disposable Kind
cluster on exit.

The `Qualify Hangar Helm Chart` GitHub workflow performs the staging and live
test for an existing image tag. Use the `preview-<branch>` tag produced by a
manual `Publish Hangar Containers` run to qualify changes without creating a
release tag. Before the qualification workflow is present on the default
branch, enable `run_helm_e2e` on the manual container publication; the publisher
invokes the same reusable qualification workflow after every preview image has
been published. The release workflow runs the same test automatically and will
not attest, sign, or publish the candidate chart if it fails.
