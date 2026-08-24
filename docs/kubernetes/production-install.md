# Prepare a production-profile installation

This guide describes how to configure the Hangar Helm chart with external
stateful services. It is intended for platform engineers participating in
production qualification and design review.

> [!CAUTION]
> Hangar `0.1.0-rc.30` is not supported for production. The production profile
> renders with secure defaults, but it has not completed the installation,
> upgrade, backup/restore, failure-recovery, security-review, or compatibility
> gates required for production support. Do not place critical data or users on
> this release.

## Architecture

The production profile deploys only Hangar application workloads:

- web, administration, and spaces frontends;
- API and Live services;
- task and beat workers; and
- one revision-scoped migration Job.

You must provide PostgreSQL, a Redis-compatible Valkey service, RabbitMQ, and
S3-compatible object storage. Kubernetes ingress replaces the standalone Hangar
proxy image.

## 1. Record the qualification environment

Before rendering the chart, record:

- Kubernetes server version and distribution;
- Helm version;
- node architecture;
- ingress-controller name and version;
- CNI name, version, and `NetworkPolicy` enforcement mode;
- CSI driver and storage backend used by any cluster-local infrastructure;
- external-service products, versions, endpoints, and TLS modes; and
- backup, restore, retention, and recovery-point procedures.

The current chart boundary is Kubernetes 1.30–1.36, including Kubernetes 1.36.2,
Helm 4.2, and AMD64. A complete external-service version matrix has not yet been
published.

## 2. Provision external services

Provision dedicated, least-privilege identities for Hangar:

| Service        | Required interface                                            | Operator responsibilities                                                   |
| -------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------- |
| PostgreSQL     | Authenticated PostgreSQL URL                                  | Database lifecycle, TLS, backups, restore tests, capacity, and availability |
| Valkey         | Authenticated Redis-protocol URL                              | TLS, persistence, eviction policy, capacity, and availability               |
| RabbitMQ       | Authenticated AMQP URL                                        | TLS, virtual host, queue durability, capacity, and availability             |
| Object storage | HTTPS S3-compatible endpoint, bucket, region, and credentials | Bucket policy, versioning, encryption, lifecycle, backups, and availability |

Hangar's current Celery/Kombu stack can create transient, non-exclusive reply
queues. Verify compatibility with your RabbitMQ release. RabbitMQ 4.x may require
the `transient_nonexcl_queues` deprecated feature to be permitted until the
application stack no longer declares those queues.

Do not use provider administrator credentials. Restrict every identity to the
single database, cache scope, virtual host, or bucket required by Hangar.

## 3. Establish network paths

The chart applies default-deny ingress and egress policies. Public HTTPS egress
on TCP 443 is allowed, while private, loopback, link-local, carrier-grade NAT,
and cluster address ranges are denied unless explicitly listed.

For each private dependency, add the narrowest destination CIDR and port to
`networkPolicy.privateEgress`. Do not add an entire RFC1918 range when a `/32` or
smaller routed subnet is available.

Confirm that:

- DNS resolves dependencies to the intended addresses;
- service-side TLS certificates validate from the Hangar Pods;
- cloud firewalls and security groups admit only the required sources;
- the selected CNI enforces both IPv4 and IPv6 policy as applicable; and
- no dependency management interface is exposed through the Hangar Ingress.

## 4. Create the namespace and TLS Secret

```bash
export CHART_VERSION=0.1.0-rc.30
export RELEASE_NAME=hangar
export NAMESPACE=hangar
export HANGAR_HOST=hangar.example.com

kubectl create namespace "$NAMESPACE"
kubectl label namespace "$NAMESPACE" \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted

kubectl --namespace "$NAMESPACE" create secret tls hangar-tls \
  --cert=/secure/path/tls.crt \
  --key=/secure/path/tls.key
```

Use your certificate-management system instead when it owns the TLS Secret.

## 5. Create application Secrets

Create these resources through an external secret operator or another managed
secret-delivery workflow:

| Default Secret          | Required key                                 | Consumer                     |
| ----------------------- | -------------------------------------------- | ---------------------------- |
| `hangar-application`    | `SECRET_KEY`                                 | API, workers, migrator       |
| `hangar-live`           | `LIVE_SERVER_SECRET_KEY`                     | Live and general worker      |
| `hangar-database`       | `DATABASE_URL`                               | API, workers, migrator       |
| `hangar-cache`          | `REDIS_URL`                                  | API, Live, workers, migrator |
| `hangar-queue`          | `AMQP_URL`                                   | API and workers              |
| `hangar-object-storage` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | API and task worker          |

The chart references existing Secrets. It does not generate credentials, read
Secrets through Kubernetes RBAC, or copy secret values into the Helm release.
Avoid `--set` for credentials and do not commit populated Secret manifests.

If the object-storage `publicEndpoint` resolves to private address space from
the Live pod, add only its exact hostname to `live.pdfAssetAllowedHosts`.
Normally `publicEndpoint` is the public Hangar/object-storage origin and this
allowlist remains empty.

Encode reserved characters in connection URLs. Require transport security at
each external-service boundary; the chart cannot add TLS to a plaintext
connection URL.

## 6. Prepare production values

Download the release-matched example:

```bash
curl --fail --location --silent --show-error \
  --output production-values.yaml \
  https://raw.githubusercontent.com/szymczag/hangar/hangar-v0.1.0-rc.30/charts/hangar/examples/production-values.yaml
```

At minimum, set:

- `publicUrl.host`;
- `ingress.className`, TLS Secret, and controller annotations;
- `externalServices.objectStorage` internal/public endpoints, public upload
  bucket, private import bucket, region, and addressing mode;
- `todoistImports`, leaving it disabled unless the private bucket, PostgreSQL,
  Valkey, RabbitMQ, Beat, dedicated worker capacity, and monitoring have been
  qualified together;
- the `networkPolicy.ingressController` preset and DNS selectors for your
  cluster; and
- `networkPolicy.privateEgress` for every private dependency address and port.

Review the [configuration reference](configuration.md) before changing replicas,
resources, scheduling, PDBs, application policy, or observability settings.

## 7. Render and review

```bash
helm template "$RELEASE_NAME" oci://ghcr.io/szymczag/charts/hangar \
  --version "$CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values production-values.yaml \
  > rendered.yaml
```

The review must confirm that:

- every Hangar image is referenced by an immutable digest;
- no bundled PostgreSQL, Valkey, RabbitMQ, or object-storage workload renders;
- every workload uses the Restricted-compatible security context;
- no RBAC resource or ServiceAccount token mount renders;
- all expected NetworkPolicies render with correct selectors and CIDRs;
- the Ingress uses the intended hostname, class, TLS Secret, and annotations;
- resource requests and limits match the capacity plan; and
- `todoistImports.enabled=true` renders exactly one dedicated `imports`-queue
  worker group with bounded concurrency/prefetch and no public import-bucket route;
- no Secret value appears in `rendered.yaml`.

Run policy and admission checks used by the target cluster against this rendered
file before installation.

## 8. Install in a qualification environment

Only proceed in a non-critical qualification environment with tested backups:

```bash
helm upgrade --install "$RELEASE_NAME" \
  oci://ghcr.io/szymczag/charts/hangar \
  --version "$CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values production-values.yaml \
  --rollback-on-failure \
  --wait \
  --wait-for-jobs \
  --timeout 20m
```

Follow [installation verification](operations.md#verify-a-release), then test
authentication, project operations, uploads, object downloads, WebSockets,
background tasks, email or webhook integrations in scope, and negative network
paths.

## Production acceptance gates

Do not describe a production-profile installation as supported until evidence
exists for all of the following:

- clean install with the exact external-service versions;
- upgrade from the minimum supported Hangar version;
- coordinated PostgreSQL and object-storage backup and clean-environment restore;
- recovery from a deliberately failed migration;
- documented rollback decisions for compatible and incompatible migrations;
- ingress routing, WebSockets, trusted headers, request limits, and TLS redirects;
- credential rotation without secret disclosure;
- vulnerability, license, SBOM, provenance, and signature review;
- positive and negative CNI policy tests; and
- sustained workload, disruption, and capacity tests.

The normative status is maintained in the
[release qualification checklist](../kubernetes-deployment-plan.md#release-qualification-checklist).
