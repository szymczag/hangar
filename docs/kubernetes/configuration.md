# Kubernetes configuration reference

This reference describes the operator-facing values of the Hangar Helm chart.
The authoritative machine-readable constraints are in
[`values.schema.json`](../../charts/hangar/values.schema.json), and the complete
defaults are in [`values.yaml`](../../charts/hangar/values.yaml).

## Profiles

`deploymentProfile` accepts exactly `production` or `evaluation`.

| Setting                                      | Production      | Evaluation                   |
| -------------------------------------------- | --------------- | ---------------------------- |
| `deploymentProfile`                          | `production`    | `evaluation`                 |
| `evaluation.enabled`                         | `false`         | `true`                       |
| PostgreSQL, Valkey, RabbitMQ, object storage | External        | Bundled and single replica   |
| `publicUrl.scheme`                           | Must be `https` | `https` strongly recommended |
| Object-storage endpoint                      | Must use HTTPS  | Set internally by the chart  |

The profile and `evaluation.enabled` must agree. Schema validation rejects mixed
configurations.

## Top-level value groups

| Value group                               | Purpose                                                                                                 |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `global`                                  | Shared image-pull Secrets, Pod labels, and Pod annotations                                              |
| `publicUrl`                               | Canonical external scheme and host                                                                      |
| `application`                             | Allowed hosts, upload limits, signed URLs, retention, API rate limits, and webhook destination controls |
| `existingSecrets`                         | Names and keys of pre-existing Secret resources                                                         |
| `externalServices`                        | Non-secret external object-storage settings                                                             |
| `observability`                           | Optional OTLP endpoint and metrics protocol                                                             |
| `ingress`                                 | Controller class, annotations, and TLS Secret                                                           |
| `networkPolicy`                           | Ingress-controller/DNS selectors and private egress exceptions                                          |
| `podDefaults`                             | Scheduling and termination defaults shared by application Pods                                          |
| `web`, `admin`, `space`, `live`, `api`    | Images, replicas, resources, and PDBs for application services                                          |
| `worker`, `beatWorker`                    | Worker replicas, resources, and PDBs                                                                    |
| `migrator`                                | Migration timeouts, retries, retention, and resources                                                   |
| `evaluation-*`, `evaluationObjectStorage` | Bundled dependency settings for evaluation only                                                         |

## Public URL and ingress

```yaml
publicUrl:
  scheme: https
  host: hangar.example.com

ingress:
  enabled: true
  className: nginx
  annotations: {}
  tls:
    secretName: hangar-tls
```

`ingress.enabled` and TLS are mandatory. The chart is controller-neutral and
does not impose redirect, request-size, or WebSocket annotations. Configure
equivalent behavior for your controller.

The Ingress routes:

| Path                       | Backend component       |
| -------------------------- | ----------------------- |
| `/api`, `/auth`, `/static` | API                     |
| `/live`                    | Live/WebSocket service  |
| `/god-mode`                | Administration frontend |
| `/spaces`                  | Spaces frontend         |
| `/`                        | Web frontend            |

The most specific paths precede `/`. Preserve this ordering if extending the
chart.

## Application policy

| Value                                  | Default     | Constraint or effect                                       |
| -------------------------------------- | ----------- | ---------------------------------------------------------- |
| `application.allowedHosts`             | `[]`        | Additional hostnames; the public host is always configured |
| `application.fileSizeLimit`            | `5242880`   | Bytes, from 1 through 1 GiB                                |
| `application.signedUrlExpiration`      | `3600`      | Seconds, from 60 through 86400                             |
| `application.hardDeleteAfterDays`      | `60`        | Days, from 1 through 3650                                  |
| `application.apiKeyRateLimit`          | `60/minute` | Positive count per second, minute, hour, or day            |
| `application.webhookAllowedHosts`      | `[]`        | Explicit outbound webhook hostname allowlist               |
| `application.webhookAllowedCIDRs`      | `[]`        | Explicit outbound webhook network allowlist                |
| `application.webhookDisallowedDomains` | `[]`        | Explicit domain denylist                                   |

Coordinate the ingress controller's request-body limit with
`application.fileSizeLimit`. The lower limit wins.

## Secret interface

The chart stores only Secret names and key names in the Helm release.

| Value                           | Default resource        | Default key                                  |
| ------------------------------- | ----------------------- | -------------------------------------------- |
| `existingSecrets.application`   | `hangar-application`    | `SECRET_KEY`                                 |
| `existingSecrets.live`          | `hangar-live`           | `LIVE_SERVER_SECRET_KEY`                     |
| `existingSecrets.database`      | `hangar-database`       | `DATABASE_URL`                               |
| `existingSecrets.cache`         | `hangar-cache`          | `REDIS_URL`                                  |
| `existingSecrets.queue`         | `hangar-queue`          | `AMQP_URL`                                   |
| `existingSecrets.objectStorage` | `hangar-object-storage` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |

Evaluation adds dependency keys to the same resources:

| Secret            | Additional evaluation keys                                                            |
| ----------------- | ------------------------------------------------------------------------------------- |
| `hangar-database` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `USERDB_USER`, `USERDB_PASSWORD` |
| `hangar-cache`    | `VALKEY_PASSWORD`, `users.acl`                                                        |
| `hangar-queue`    | `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`, `ERLANG_COOKIE`                     |

Missing resources or keys appear as `CreateContainerConfigError`; Helm cannot
validate their contents without Secret-reading RBAC, which the chart does not
request.

## External object storage

```yaml
externalServices:
  objectStorage:
    endpoint: https://s3.example.com
    bucket: hangar
    region: eu-central-1
    pathStyle: false
```

Set `pathStyle: true` only when required by the S3-compatible provider. The
production profile requires an HTTPS endpoint. Credentials come from the
object-storage Secret, not this block.

## NetworkPolicy

`networkPolicy.enabled` is fixed to `true`. The chart renders:

- default-deny ingress and egress for all release Pods;
- ingress-controller access to public components only;
- internal Live/Space access to the API;
- application access to in-release dependencies;
- DNS access through the configured namespace and Pod selectors;
- public TCP 443 egress excluding private, reserved, cluster, metadata, and
  loopback networks; and
- explicit private egress entries.

Example private dependency exception:

```yaml
networkPolicy:
  privateEgress:
    - cidr: 10.20.30.10/32
      ports:
        - port: 5432
          protocol: TCP
```

Entries are IP-based. Kubernetes `NetworkPolicy` cannot express an FQDN
allowlist. If a dependency address changes, update the CIDR before traffic moves.
Use CNI-specific FQDN or L7 policies outside this chart only after reviewing how
they compose with the chart policies.

The default ingress-controller selector expects namespace `ingress-nginx` and
Pods labeled `app.kubernetes.io/name=ingress-nginx`. The default DNS selector
expects `kube-system` and `k8s-app=kube-dns`. Change both selectors to match the
actual cluster labels.

## Images and registry credentials

Published charts contain immutable release digests. Source-chart defaults use an
all-zero digest deliberately and cannot be installed safely without release
staging.

Use `global.imagePullSecrets` for all Hangar application images:

```yaml
global:
  imagePullSecrets:
    - name: ghcr-pull
```

Use a component's `image.pullSecrets` for a narrower credential. Worker, beat,
and migrator Pods use `api.image.pullSecrets` because they run the API image.
Public release images currently pull anonymously, so a GHCR credential is not
required for `0.1.0-rc.4`.

## Replicas and disruption budgets

| Component               | Replica rule              | Notes                                                                       |
| ----------------------- | ------------------------- | --------------------------------------------------------------------------- |
| Web, admin, space, Live | One or more               | Defaults to two; PDB enabled by default                                     |
| API                     | Exactly one               | Startup side effects must be removed before horizontal scaling is supported |
| Task worker             | One or more               | Scale only after queue and database capacity review                         |
| Beat worker             | Exactly one               | No scheduler leader election                                                |
| Migrator                | One Job per Helm revision | Bounded by deadline and retry values                                        |

Every component has resource requests and limits. Treat defaults as starting
points for evaluation, not a production sizing guarantee. Observe CPU,
memory, latency, queue depth, and dependency capacity before changing replicas.

PDBs protect only against voluntary disruptions. They do not provide application
or dependency high availability.

## Scheduling

`podDefaults` supplies shared node selectors, tolerations, affinity, topology
spread, and a termination grace period. Component templates combine these values
with their security constraints.

Evaluation dependencies are fixed to `kubernetes.io/arch: amd64`. All application
images in `0.1.0-rc.4` are also AMD64-only.

## Evaluation storage

Default requested capacities are:

| Dependency     | Capacity |
| -------------- | -------: |
| PostgreSQL     |    8 GiB |
| RabbitMQ       |    8 GiB |
| Valkey         |    4 GiB |
| Object storage |   10 GiB |

All four stateful services require persistent storage. Their PVCs are retained
where the underlying controller supports the configured retention policy. A
retained PVC is not a backup.

Set all four storage classes explicitly when a suitable default does not exist;
see [`evaluation-values.yaml`](../../charts/hangar/examples/evaluation-values.yaml).

## Observability and privacy

```yaml
observability:
  otlpEndpoint: ""
  metricsProtocol: grpc
```

An empty endpoint keeps telemetry export offline. Export requires both an
explicit HTTPS endpoint and application-level opt-in. `metricsProtocol` accepts
`grpc` or `http`. The chart does not install an OpenTelemetry collector.
