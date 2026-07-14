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
| `gateway`                                 | Gateway API creation/attachment, listener, class, and TLS Secret                                        |
| `networkPolicy`                           | Ingress-controller/DNS selectors and private egress exceptions                                          |
| `podDefaults`                             | Scheduling and termination defaults shared by application Pods                                          |
| `web`, `admin`, `space`, `live`, `api`    | Images, replicas, resources, and PDBs for application services                                          |
| `worker`, `beatWorker`                    | Worker replicas, resources, and PDBs                                                                    |
| `migrator`                                | Migration timeouts, retries, retention, and resources                                                   |
| `evaluation-*`, `evaluationObjectStorage` | Bundled dependency settings for evaluation only                                                         |

## Public URL and routing

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

`publicUrl` is canonical: it configures Django and Live, the frontend runtime
`config.js`, and all five Vite URL fallbacks. Ingress mode terminates TLS using
`ingress.tls.secretName`. The chart is controller-neutral and does not impose
request-size or WebSocket annotations.

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

For Gateway API/Envoy, use `charts/hangar/examples/gateway-values.yaml`.
`gateway.enabled: true` suppresses the Ingress. With `gateway.create: true`, the
chart creates an HTTPS listener that terminates TLS; otherwise `name`, optional
`namespace`, and `sectionName` attach routes to an existing listener. Exact
`/god-mode`, `/spaces`, `/live`, and `/api` requests are normalized with 308
redirects, and the API route overwrites forwarded scheme, host, and port headers
with the canonical HTTPS origin.

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
    publicEndpoint: https://s3.example.com
    bucket: hangar
    region: eu-central-1
    pathStyle: false
```

`endpoint` is used by API and worker Pods. `publicEndpoint` is used to construct
browser-facing presigned URLs; leave it empty only when it is identical to
`endpoint`. Set `pathStyle: true` only when required by the S3-compatible
provider. The production profile requires HTTPS for both endpoints. Credentials
come from the object-storage Secret, not this block.

The evaluation profile uses the bundled SeaweedFS service internally while
presigning browser requests against the public Hangar origin. To complete that
same-origin flow, the chart routes `/<bucket>` to the SeaweedFS S3 port and adds
a narrowly scoped ingress-controller NetworkPolicy rule for that Pod. For the
default bucket, uploads therefore use `https://<public-host>/hangar`; the request
does not go to the frontend service. Bucket names that collide with Hangar's
reserved public route prefixes are rejected by the schema.

Production does not render this proxy route. Its `publicEndpoint` must be
publicly reachable by browsers; `endpoint` may use a separate address reachable
only from the API and workers.

## NetworkPolicy

`networkPolicy.enabled` is fixed to `true`. The chart renders:

- default-deny ingress and egress for all release Pods;
- ingress-controller access to public components only;
- evaluation ingress-controller access to the bundled object-storage S3 port;
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

Ingress-controller peers are selected atomically with
`networkPolicy.ingressController.preset`. Named presets do not consume partial
selector maps: the schema requires `namespaceSelector` and `podSelector` to
remain empty, which prevents Helm's deep merge from retaining labels from
another controller.

| Preset         | Namespace                  | Pod label                                                            |
| -------------- | -------------------------- | -------------------------------------------------------------------- |
| `nginx`        | `ingress-nginx`            | `app.kubernetes.io/name=ingress-nginx`                               |
| `envoyGateway` | `envoy-gateway-system`     | `gateway.envoyproxy.io/owning-gateway-name=<effective gateway.name>` |
| `traefik`      | `traefik`                  | `app.kubernetes.io/name=traefik`                                     |
| `custom`       | operator-supplied selector | operator-supplied selector                                           |

`nginx` is the default. Gateway API cannot be enabled with the `nginx` preset.
The Envoy preset uses the explicit `gateway.name`, or the chart-generated
Gateway name when that field is empty. It selects the Envoy data-plane Pods,
not the Envoy Gateway controller.

Use `custom` when the controller is installed under different labels or in a
different namespace. Both selectors are mandatory and each must contain at
least one `matchLabels` entry:

```yaml
networkPolicy:
  ingressController:
    preset: custom
    namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: edge-system
    podSelector:
      matchLabels:
        app.kubernetes.io/component: edge-proxy
```

The DNS selector still defaults to `kube-system` and `k8s-app=kube-dns`; change
it to match the actual cluster labels.

When upgrading values that previously overrode either ingress selector, choose
a named preset or set `preset: custom` and supply both complete selectors.
Selector-only and partial overrides are rejected instead of being deep-merged
with a controller preset.

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
required for `0.1.0-rc.7`.

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
images in `0.1.0-rc.7` are also AMD64-only.

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
