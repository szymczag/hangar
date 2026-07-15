# Hangar Helm chart

This directory contains the Hangar-owned Helm chart for Kubernetes. The chart is
published as an OCI artifact at:

```text
oci://ghcr.io/szymczag/charts/hangar
```

The latest published chart is `0.1.0-rc.10` (`appVersion: v0.1.0-rc.10`). Its
evaluation profile is live-qualified on AMD64. It is a prerelease and is not yet
supported for production. Release packaging stages these versions and immutable
image digests from the release tag; source defaults remain fail-closed.

## Start here

- [Kubernetes documentation](../../docs/kubernetes/README.md)
- [Evaluation installation tutorial](../../docs/kubernetes/evaluation-install.md)
- [Production-profile qualification guide](../../docs/kubernetes/production-install.md)
- [Configuration reference](../../docs/kubernetes/configuration.md)
- [Operations](../../docs/kubernetes/operations.md)
- [Security and artifact verification](../../docs/kubernetes/security.md)
- [Troubleshooting](../../docs/kubernetes/troubleshooting.md)
- [Secure email and OpenPGP operations](../../docs/aws-ses-email-operations.md)

Inspect the published chart without registry credentials:

```bash
helm show chart oci://ghcr.io/szymczag/charts/hangar \
  --version 0.1.0-rc.10
```

Do not use `0.1.0-rc.1` or `0.1.0-rc.2`; those immutable versions were consumed
by incomplete release attempts. `0.1.0-rc.9` is the previous complete release.

## Deployment profiles

| Profile      | Stateful services                                        | Intended use                   | Status                                   |
| ------------ | -------------------------------------------------------- | ------------------------------ | ---------------------------------------- |
| `evaluation` | Bundled PostgreSQL, Valkey, RabbitMQ, and object storage | Labs and compatibility testing | Live-qualified on AMD64                  |
| `production` | Operator-managed external services                       | Durable deployment model       | Available for qualification, unsupported |

Both profiles use the same Hangar application images, Restricted-compatible
security contexts, pre-existing Secret interface, public routing, and
default-deny NetworkPolicies.

## Optional secure email workload

Secure email is disabled by default. Setting `mail.enabled=true` adds a dedicated
`mail-worker` for Amazon SES API submission, feedback processing, audit receipts,
suppression handling, and optional OpenPGP encryption. Only that workload receives
the mail service account or optional SES/SQS credential references; the chart does
not create AWS identities, queues, topics, configuration sets, or DNS records.

Before enabling it, read the
[email security model](../../docs/email-delivery-and-openpgp.md), configure the
required resources with the
[SES operations guide](../../docs/aws-ses-email-operations.md), and review the
[Helm values and Secret contract](../../docs/kubernetes/configuration.md#secure-email-delivery).

## Optional Todoist import workload

Todoist imports are disabled by default. Setting `todoistImports.enabled=true`
renders a dedicated `import-worker` that consumes only the `imports` queue and
receives the private import-bucket credential interface. The values contract
also bounds API rates, concurrent user/workspace jobs, rolling workspace rows,
active source bytes, worker concurrency/prefetch, resources, replicas, and an
optional PDB. Invalid rates or numeric ranges are rejected during rendering.

Before enabling it, provision and test the distinct private import bucket, apply
the database migration, and verify PostgreSQL, Valkey, RabbitMQ, the Beat worker,
and the import worker. Follow the
[operator configuration](../../docs/kubernetes/configuration.md#todoist-import-admission-and-worker),
[runbook](../../docs/kubernetes/operations.md#operate-todoist-imports), and
[user/security guide](../../docs/importing-from-todoist.md).

## Prerequisites

- Kubernetes 1.30 through 1.36, including 1.36.2;
- Helm 4.2;
- AMD64 nodes;
- a TLS-enabled ingress controller or Gateway API implementation with WebSocket support;
- a CNI that enforces `NetworkPolicy`;
- pre-existing application and TLS Secrets; and
- a default `StorageClass` or explicit storage classes for evaluation.

The chart does not install cluster infrastructure such as an ingress/Gateway controller,
cert-manager, CNI, CSI driver, external secret operator, or telemetry collector.

Product help links are configured under `branding`. Documentation, issue, and
private-security-report links default to the Hangar GitHub repository. Set
`branding.termsUrl` and `branding.privacyUrl` only when the operator has applicable
policies; empty values make the UI show the AGPL source notice instead of inventing
vendor terms or a support relationship.

## Release packages and source checkouts

Install only a published release package. Published packages contain immutable
digests for the five Hangar application images. The source chart intentionally
contains all-zero application digests so an unstaged source checkout fails
closed.

Release `0.1.0-rc.10` is available from the
[GitHub Release](https://github.com/szymczag/hangar/releases/tag/hangar-v0.1.0-rc.10)
and GHCR. Follow the [verification guide](../../docs/kubernetes/security.md)
before admitting the package to a controlled environment.

## Chart layout

| Path                       | Purpose                                                          |
| -------------------------- | ---------------------------------------------------------------- |
| `Chart.yaml`, `Chart.lock` | Chart metadata and locked evaluation dependencies                |
| `charts/`                  | Vendored dependency archives                                     |
| `values.yaml`              | Complete source defaults with fail-closed application digests    |
| `values.schema.json`       | Helm value validation and security invariants                    |
| `examples/`                | Production and evaluation operator examples                      |
| `templates/`               | Hangar workloads, Services, Ingress, policies, and migration Job |
| `scripts/`                 | Dependency verification and release staging                      |
| `tests/`                   | Render-policy and ephemeral-cluster qualification harnesses      |
| `DEPENDENCIES.md`          | Dependency hashes, image digests, and qualification toolchain    |

## Canonical public URL and Gateway API

`publicUrl` is the installation's single external origin. The chart uses it for
backend host/CORS settings, Live, all five frontend URL variables, TLS host
matching, and a generated runtime `config.js`. Published frontend images also
bake the default origin as a fallback, while the runtime file lets an operator
change the hostname without rebuilding static assets.

Set `gateway.enabled: true` to use Gateway API. This suppresses the NGINX
`Ingress` and renders explicit routes for `/god-mode/`, `/spaces/`, `/live/`,
`/api/`, and `/`; exact paths without their trailing slash receive a 308
method-preserving redirect. See `examples/gateway-values.yaml` for an
Envoy-backed Gateway with TLS termination. Gateway users must also choose the
matching `networkPolicy.ingressController.preset`; the schema rejects Gateway
API with the default `nginx` preset.

Evaluation installs additionally route the configured `/<bucket>` path to the
bundled SeaweedFS S3 service so browser presigned uploads do not fall through to
the web frontend. The separate `externalServices.objectStorage.importBucket` is
server-only and is never added to Ingress or Gateway routes.

## Validate a source change

Dependencies are vendored and locked so validation does not silently select a
new upstream chart.

```bash
charts/hangar/scripts/verify-dependencies.sh
charts/hangar/tests/render-policy.sh
```

CI additionally runs Helm linting and packaging, negative schema cases,
Kubernetes 1.36.2 schema validation, kube-linter security checks, and shell syntax
tests.

The source chart cannot be passed directly to the live harness because its
application digests are invalid by design. Maintainers stage release or preview
image digests with `charts/hangar/scripts/prepare-release.sh`, then run:

```bash
mkdir -p .local/hangar-e2e-bin
charts/hangar/tests/install-e2e-tools.sh .local/hangar-e2e-bin
PATH="$PWD/.local/hangar-e2e-bin:$PATH" \
  charts/hangar/tests/e2e-kind.sh /path/to/staged/hangar-chart
```

The harness creates an ephemeral AMD64 Kind cluster and exercises the evaluation
profile. It is destructive only to that disposable cluster.

## Security invariants

Chart changes must preserve:

- immutable release image digests;
- non-root, read-only, Restricted-compatible workloads;
- no chart-created RBAC or ServiceAccount token mounts;
- pre-existing Secrets rather than Helm-managed credential values;
- mandatory TLS ingress or Gateway routing and NetworkPolicy;
- bounded, revision-scoped migration Jobs; and
- privacy-by-default application configuration.

The normative implementation and release requirements are maintained in the
[Kubernetes delivery plan](../../docs/kubernetes-deployment-plan.md).
