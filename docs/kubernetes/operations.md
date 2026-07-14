# Operate a Hangar Helm release

This guide covers routine verification, upgrades, credential rotation, backup,
restore, rollback decisions, scaling, and removal. Commands use the default
release name `hangar`; adjust them for your installation.

```bash
export RELEASE_NAME=hangar
export NAMESPACE=hangar
```

## Verify a release

Start with Helm and controller state:

```bash
helm --namespace "$NAMESPACE" status "$RELEASE_NAME"
kubectl --namespace "$NAMESPACE" get \
  deployment,statefulset,pod,job,pvc,service,ingress,networkpolicy
kubectl --namespace "$NAMESPACE" rollout status deployment \
  --selector app.kubernetes.io/instance="$RELEASE_NAME" \
  --timeout=5m
```

The migration is a revision-scoped Job. A completed Job is intentionally not a
Ready Pod, so do not wait for every release Pod to report Ready.

```bash
kubectl --namespace "$NAMESPACE" get jobs \
  --selector app.kubernetes.io/instance="$RELEASE_NAME",app.kubernetes.io/component=migrator
```

Inspect the current revision's migration log by substituting its Job name:

```bash
kubectl --namespace "$NAMESPACE" logs job/HANGAR-MIGRATION-JOB
```

Then verify through the public origin:

- HTTP redirects to HTTPS;
- `/`, `/api`, `/live`, `/god-mode`, and `/spaces` reach the intended backend;
- the Live WebSocket performs an HTTP Upgrade;
- authentication and a representative project operation work;
- an uploaded object can be downloaded; and
- internal Services are not reachable outside the cluster.

When `mail.enabled=true`, also verify the dedicated mail worker, one cleartext
account receipt, one encrypted compatibility test, a simulated bounce, the
SNS/SQS feedback path, and both the user and administrator delivery ledgers.
Use [Amazon SES email operations](../aws-ses-email-operations.md) for rollout,
deliverability monitoring, suppression recovery, and incident procedures.

## Upgrade a release

### Upgrade from `rc.7` to `rc.8`

Treat this upgrade as data-affecting. Before rendering the target release:

1. take a coordinated PostgreSQL and object-storage backup and prove it can be
   restored into an isolated environment;
2. disable OIDC and SAML login and prepare authoritative stable-subject mappings
   according to the
   [federated SSO migration guide](../federated-sso-security.md); apply and review
   the mappings after the schema migration and before re-enabling either provider;
   do not infer bindings from matching email addresses;
3. if secure email will be enabled, complete the SES, SQS, DNS, IAM, Secret, and
   retention prerequisites in the
   [SES operations guide](../aws-ses-email-operations.md); and
4. if Todoist imports will be enabled, configure and verify the distinct private
   import bucket described by the [configuration reference](configuration.md).

The migration Job applies database migrations `db.0122` through `db.0124`,
`license.0008`, and `ext.0004` through `ext.0006`. Runner hardening intentionally
stops if existing installation or audit records lack required actor, target, or
consent evidence. Investigate and preserve that evidence; do not delete records
merely to make the migration pass.

After the upgrade, verify ordinary and federated authentication, representative
project writes, uploads, background work, and any enabled email or import path.
Application rollback to `rc.7` is not qualified after these migrations. Restore
the coordinated pre-upgrade recovery point into a clean environment if a return
to `rc.7` is required.

### 1. Read release-specific constraints

Read the target GitHub Release and the
[Kubernetes support boundary](README.md#support-boundary). Confirm that the
current version is an allowed upgrade source and whether its database migration
is backward-compatible.

Do not upgrade from `plane-ce` by changing only the chart reference. Hangar does
not define that migration path.

### 2. Verify artifacts

Follow [security and artifact verification](security.md) for the target chart
and images. Record the chart version and OCI digest in the change request.

### 3. Create a coordinated recovery point

Back up PostgreSQL and object storage so both represent the same application
recovery point. Record:

- backup identifiers and timestamps;
- application and chart version;
- external-service versions;
- restoration encryption keys or key references; and
- the tested restore procedure.

Do not treat Helm history, retained PVCs, or a database-only backup as a complete
Hangar recovery point.

### 4. Render and compare

```bash
export TARGET_CHART_VERSION=REPLACE_ME

helm --namespace "$NAMESPACE" get manifest "$RELEASE_NAME" \
  > current-rendered.yaml

helm template "$RELEASE_NAME" oci://ghcr.io/szymczag/charts/hangar \
  --version "$TARGET_CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values production-values.yaml \
  > target-rendered.yaml

diff --unified current-rendered.yaml target-rendered.yaml
```

Review workload images and digests, environment sources, Ingress, Services,
NetworkPolicies, security contexts, resource changes, and migration settings.
Rendered output must not contain Secret values.

### 5. Upgrade atomically

```bash
helm upgrade "$RELEASE_NAME" oci://ghcr.io/szymczag/charts/hangar \
  --version "$TARGET_CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values production-values.yaml \
  --rollback-on-failure \
  --wait \
  --wait-for-jobs \
  --timeout 20m
```

Use the evaluation values file for an evaluation release. The migrator waits for
the configured database endpoint, retries within bounded limits, and must finish
before Helm reports success.

### 6. Run post-upgrade checks

Repeat [release verification](#verify-a-release), then test authentication,
representative writes, an upload and download, WebSockets, and background work.
Confirm that a new migration Job exists for the new Helm revision.

## Respond to a failed migration

1. Stop retrying the upgrade until the failure is understood.
2. Preserve the Job name, Pod status, events, and redacted migration logs.
3. Confirm database reachability and that `DATABASE_URL` exists, without printing
   its value.
4. Determine whether the migration made any schema or data changes.
5. Follow the target release's migration recovery procedure.

Do not delete the failed Job merely to make Helm appear healthy. Do not run the
migration entrypoint manually against production data unless the release-specific
recovery procedure explicitly requires it.

## Decide between Helm rollback and data restore

`helm rollback` restores Kubernetes resources. It does not undo database
migrations, object writes, queue state, or external-service configuration.

| Situation                                           | Action                                                                                        |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Upgrade failed before any incompatible state change | Roll back to the prior Helm revision, then verify                                             |
| Migration is documented as backward-compatible      | Rollback may be used after release-specific review                                            |
| Migration changed schema or data incompatibly       | Restore the coordinated backup into a clean environment and deploy the matching chart version |
| Compatibility is unknown                            | Treat it as incompatible; do not guess                                                        |

To inspect Helm history:

```bash
helm --namespace "$NAMESPACE" history "$RELEASE_NAME"
```

When rollback is safe:

```bash
helm --namespace "$NAMESPACE" rollback "$RELEASE_NAME" REVISION \
  --wait \
  --timeout 20m
```

Always repeat application-flow tests after rollback.

## Back up and restore

### Production profile

The chart does not orchestrate application-consistent backups. Use native,
supported tooling for PostgreSQL and the object-storage provider.

A valid exercise must:

1. prevent or account for writes while selecting a common recovery point;
2. back up PostgreSQL and uploaded objects;
3. restore into clean services or isolated recovery targets;
4. deploy the chart version matching the backup;
5. verify authentication, representative projects, uploads, downloads, and
   background jobs; and
6. record actual recovery-point and recovery-time results.

Cache and transient queue state may be reconstructed only when the application
and release procedure explicitly permit it. Durable queue state and provider
configuration still require an operator decision.

### Evaluation profile

Evaluation uses four retained PVCs. Snapshot PostgreSQL and object-storage
volumes only with a CSI driver and backend whose crash/application consistency
has been tested. Copying files from live volumes is not a supported backup.

PVC retention reduces accidental deletion risk; it does not create a separate
copy and is not a backup.

## Rotate credentials

Updating a Secret does not automatically restart its consumers.

| Credential                 | Workloads to restart or replace                                       |
| -------------------------- | --------------------------------------------------------------------- |
| `SECRET_KEY`               | API, worker, beat worker; invalidate sessions and retest signed links |
| `LIVE_SERVER_SECRET_KEY`   | Live                                                                  |
| `DATABASE_URL`             | API, worker, beat worker, and the next migrator Job                   |
| `REDIS_URL`                | API, Live, worker, beat worker, and the next migrator Job             |
| `AMQP_URL`                 | API, worker, beat worker                                              |
| Object-storage credentials | API and worker                                                        |

Use the dependency provider's overlap procedure when old and new credentials can
coexist:

1. create the new provider credential;
2. update the managed Kubernetes Secret;
3. restart only affected Deployments;
4. wait for rollout and exercise the affected flow;
5. revoke the old provider credential; and
6. verify that logs and events contain no credential values.

Restart an affected Deployment with:

```bash
kubectl --namespace "$NAMESPACE" rollout restart deployment/DEPLOYMENT_NAME
kubectl --namespace "$NAMESPACE" rollout status deployment/DEPLOYMENT_NAME \
  --timeout=5m
```

Treat database and object-storage rotations as maintenance operations when the
provider cannot support overlap.

## Scale workloads

Change replicas through a values file and `helm upgrade`, not with an imperative
`kubectl scale`, so Helm remains the source of desired state.

- Web, admin, space, Live, and task workers accept one or more replicas.
- API replicas are fixed at one for this release.
- Beat worker replicas are fixed at one because scheduler leader election is not
  implemented.
- Evaluation dependencies are single replica.

Review resource usage, database connections, queue throughput, PDB behavior, and
node capacity before increasing replicas.

## Uninstall

```bash
helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE"
```

Production external services and their data are not deleted. Evaluation PVCs are
intentionally retained where supported. Inventory them after uninstall:

```bash
kubectl --namespace "$NAMESPACE" get pvc
```

Delete PVCs or the namespace only after confirming that no recovery or forensic
need remains. Namespace deletion also removes Secrets and the TLS certificate.
