# Hangar Kubernetes and Helm delivery plan

Status: release-candidate implementation; evaluation profile live-qualified,
not yet supported for production.

Last reviewed: 2026-07-13.

## Implementation snapshot

The first implementation now exists under `charts/hangar`. It includes locked
and vendored evaluation dependencies, production and evaluation profiles, JSON
Schema validation, restricted workload security contexts, default-deny network
policies, revision-scoped migrations, operator documentation, render-policy
tests, Kubernetes schema validation, security linting, OCI publication, and
release attestation and keyless Cosign signing wiring. The ephemeral-cluster
qualification harness installs the evaluation profile with exact staged
application image digests. Evaluation dependencies render only lowercase
DNS-compatible resource names, and the chart-owned object store consumes an
existing Secret rather than generating credentials.

The public `0.1.0-rc.3` prerelease is available from GHCR and its GitHub Release.
[Publication run 29278653303](https://github.com/szymczag/hangar/actions/runs/29278653303)
completed image and chart publication, the live evaluation gate, provenance
attestation, keyless signing and verification, checksum generation, and release
creation. Post-release checks confirmed anonymous chart access and full pulls of
the five digest-pinned Kubernetes application images. A clean post-publication
installation remains a separate open qualification gate.

The `0.1.0-rc.4` candidate expands the declared Kubernetes range through 1.36.
Both profiles render and validate against Kubernetes 1.36.2 schemas. The live
evaluation harness uses Kind 0.32.0's official Kubernetes 1.36.1 node image and
a checksum-pinned kubectl 1.36.2 client.

The runtime images and entrypoints have also been hardened for fixed non-root
identities, read-only-root-filesystem operation, stable self-managed identity,
bounded dependency waits, and privacy-by-default startup.
Focused unit tests cover release-discovery opt-in, telemetry enqueue behavior,
form-value parsing, and the privacy-preserving model default.

Release-candidate configuration must render integer-valued environment settings
as exact decimal strings so Helm client implementation details cannot change the
application input. Bundled Valkey health probes must authenticate against the
local process over loopback; probing through its readiness-gated Service creates
a circular dependency and is forbidden. The evaluation `hangar-cache` Secret
therefore carries a probe-only `VALKEY_PASSWORD` in addition to the application
`REDIS_URL` and mounted `users.acl` file.
The migrator also receives `REDIS_URL` because Django imports the Celery module
while loading settings for management commands. It receives only the cache URL
in addition to its core application and database keys; queue and object-storage
credentials remain outside the migration Job's trust boundary.
API HTTP probes send the configured public hostname explicitly. Pod IPs must not
be added to `ALLOWED_HOSTS` merely to accommodate kubelet probes, and the chart
must not use a wildcard host policy.

The evaluation profile passed its complete AMD64 ephemeral-cluster qualification
on 2026-07-13 in [GitHub Actions run 29272669799](https://github.com/szymczag/hangar/actions/runs/29272669799).
The run covered a Restricted namespace, migrations, HTTPS ingress, a real
WebSocket upgrade, positive and negative Cilium policies, dependency
connectivity, object-storage persistence, a rollback-on-failure upgrade, a
second migration, post-upgrade health, uninstall, and retained PVCs.

This implementation is intentionally still unsupported for production.
Production-profile installation, application-level uploads and background work,
coordinated backup/restore, migration-failure recovery, vulnerability, license,
post-publication installation, and supported-version matrix qualification remain
release gates. Source-chart application digests are fail-closed placeholders and
are replaced with resolved manifest digests only by the release workflow.

## Purpose and audience

This document defines the architecture, security contract, implementation work,
and release evidence required to ship Hangar as a supported Kubernetes deployment.
It is both a reference for the intended Helm interface and an implementation plan
for Hangar maintainers, platform engineers, security reviewers, and release
engineers.

Kubernetes support is a separate product surface. It must not be described as
supported merely because the application can be rendered from an upstream chart
or made to start in a development cluster. Support begins only when every release
gate in this document passes against the exact chart and image digests being
published.

The words **must**, **must not**, **required**, and **supported** are normative in
this document. Items described as recommendations are operator choices rather
than chart guarantees.

## Support boundary

The first supported Helm release will include two profiles:

| Profile      | Intended use                             | Stateful services                                                | Support statement                                                    |
| ------------ | ---------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------- |
| `production` | Durable, security-reviewed installations | External PostgreSQL, Valkey, RabbitMQ, and S3-compatible storage | Supported after all qualification gates pass                         |
| `evaluation` | Evaluation and non-critical testing      | Bundled, pinned dependencies with persistent storage             | Shipped and tested, but not a production availability recommendation |

Both profiles must run the same Hangar application images and security contexts.
The evaluation profile must not weaken application workload security.

This plan covers:

- hardening Hangar's runtime images for Kubernetes;
- creating and maintaining a clean, Hangar-owned Helm chart;
- defining the chart values, configuration, and Secret interfaces;
- ingress, egress, workload, and namespace isolation;
- external production services and bundled evaluation dependencies;
- installation, migration, upgrade, backup, restore, and rollback behavior;
- chart validation and ephemeral-cluster testing;
- OCI publication, provenance, attestations, and keyless signing; and
- retiring inherited Plane deployment automation and documentation.

This plan does not cover:

- provisioning or operating a Kubernetes cluster;
- installing an ingress controller, CNI, CSI driver, certificate manager, or
  Secret operator;
- managing a user's external PostgreSQL, Valkey, RabbitMQ, or object-storage
  service;
- deploying from GitHub Actions into a production or user-managed cluster;
- providing a general-purpose database or message-queue operator; or
- promising high availability for the evaluation profile.

## Baseline state and changes made

Before this implementation, Hangar did not ship a Kubernetes deployment. The
`deployments/kubernetes/community` directory links to Plane's separately
maintained chart and contains no Hangar chart or Kubernetes manifests. The new
Hangar-owned chart is independent of that inherited directory, and the main
README now links to the Hangar chart documentation.

The inherited `.github/workflows/feature-deployment.yml` workflow was not an
acceptable Hangar deployment path. It includes Plane-specific configuration,
external deployment assumptions, and Kubernetes commands that skip TLS
verification. Its root job is now explicitly disabled and it is not reused for
chart qualification or deployment.

Hangar's release workflow publishes AMD64 component images for `web`, `admin`,
`space`, `live`, `api`, and `proxy`, plus an all-in-one image. ARM64 is outside
the supported release contract until every application and evaluation
dependency is qualified for that architecture. The supported Kubernetes
architecture will use:

- `hangar-web`;
- `hangar-admin`;
- `hangar-space`;
- `hangar-live`; and
- `hangar-api` for the API, worker, beat worker, and migration Job.

Kubernetes ingress replaces `hangar-proxy`. The `hangar-aio` image is not part of
the supported component architecture.

The initial implementation addressed the following image and startup blockers:

- web and admin now use the unprivileged Nginx runtime;
- space, Live, and API now declare fixed non-root runtime users;
- API code and runtime directories no longer use world-writable permissions;
- writable paths are explicit volumes under a read-only root filesystem, with
  cluster-level verification still required;
- API startup now uses a stable self-managed identity instead of pod-local
  hardware or filesystem state;
- release discovery is opt-in and telemetry defaults to disabled;
- frontend endpoint values now use a same-origin route contract, which still
  requires browser qualification against the release images;
- Live has dedicated readiness and liveness probes, which still require failure
  and WebSocket-draining qualification; and
- API, worker, and beat dependency and migration waits are bounded.

These are application and image prerequisites, not problems that should be hidden
with privileged chart settings.

## Target deployment architecture

### Workload contract

The chart will create only namespaced resources. Application workloads receive no
Kubernetes API permissions and do not need a ServiceAccount token.

| Component   | Kubernetes object   | Service              | Public route               | Required dependencies                                    | Scaling notes                                                             |
| ----------- | ------------------- | -------------------- | -------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------- |
| Web         | Deployment          | ClusterIP, port 3000 | `/`                        | API through the public origin                            | Horizontally scalable after session behavior is verified                  |
| Admin       | Deployment          | ClusterIP, port 3000 | `/god-mode`                | API through the public origin                            | Horizontally scalable                                                     |
| Space       | Deployment          | ClusterIP, port 3000 | `/spaces`                  | API through the public origin                            | Horizontally scalable after server-rendering behavior is verified         |
| Live        | Deployment          | ClusterIP, port 3000 | `/live`                    | API and Valkey                                           | WebSocket-aware draining is required                                      |
| API         | Deployment          | ClusterIP, port 8000 | `/api`, `/auth`, `/static` | PostgreSQL, Valkey, RabbitMQ, object storage             | Horizontally scalable after startup side effects are removed              |
| Worker      | Deployment          | None                 | None                       | PostgreSQL, Valkey, RabbitMQ, object storage             | Scaled separately from API                                                |
| Beat worker | Deployment          | None                 | None                       | PostgreSQL, Valkey, RabbitMQ                             | Exactly one active scheduler until a tested leader-election design exists |
| Migrator    | revision-scoped Job | None                 | None                       | PostgreSQL and configuration needed to initialize Django | Exactly one successful migration per Helm revision                        |

No application Service uses `NodePort`, `LoadBalancer`, `hostPort`, or
`externalIPs` by default. Stateful management consoles and metrics endpoints are
never included in public ingress.

### Request routing contract

The Ingress implementation must preserve the behavior currently supplied by the
component proxy without installing an ingress controller.

| Path                         | Destination | Required behavior                                                                  |
| ---------------------------- | ----------- | ---------------------------------------------------------------------------------- |
| `/`                          | Web         | Single-page application fallback                                                   |
| `/god-mode` and `/god-mode/` | Admin       | Canonical trailing-slash redirect and nested route fallback                        |
| `/spaces` and `/spaces/`     | Space       | Canonical trailing-slash redirect and server-rendered routes                       |
| `/api`                       | API         | Request bodies limited consistently with Hangar's upload setting                   |
| `/auth`                      | API         | Correct public scheme and host for OAuth and SSO callbacks                         |
| `/static`                    | API         | Static response routing without exposing application filesystems                   |
| `/live`                      | Live        | HTTP and WebSocket upgrades, long-lived connection timeouts, and graceful draining |

Production examples require HTTPS and a user-supplied TLS Secret. The chart must
support an ingress class, host names, TLS Secret names, and controller-specific
annotations without assuming a particular controller. Redirect, body-size,
WebSocket, and timeout behavior must be tested with each ingress controller named
as supported.

The API and frontend components must use the same public origin by default. A
release image is reusable only if empty frontend base URLs produce correct
same-origin requests with the documented base paths. If that behavior cannot be
proven, runtime frontend configuration must be implemented and tested before the
chart can ship; per-installation frontend image builds are not supported.

The evaluation profile may expose an object-storage data route only when the
application's upload and download behavior requires it. That route must expose
only the data plane and configured bucket path. The object-storage administration
console must remain private. Production uses the operator's external object
storage endpoint and does not proxy it automatically.

### Dependency contract

Production requires operator-managed services. The chart configures connections
but does not create, upgrade, back up, or repair those services. Supported
combinations and minimum server versions must be recorded during Phase 0 and
tested in release qualification.

The evaluation profile uses vetted third-party subcharts pinned in `Chart.yaml`
and `Chart.lock`. Qualification also records the resolved dependency image
digests; a chart lock alone does not make dependency images immutable. Evaluation
credentials must be supplied through pre-existing Secrets, not generated with
Helm template functions or committed to values files.

PersistentVolumeClaims are enabled for every evaluation dependency. Uninstall
must retain persistent data by default and print explicit cleanup instructions.
The chart must never claim that a single-replica bundled dependency is highly
available.

## Normative security requirements

Requirement identifiers are stable references for pull requests, tests, and
release evidence.

### Kubernetes and workload isolation

- **K8S-01:** The chart creates namespaced resources only and requires no
  cluster-administrator permissions.
- **K8S-02:** The chart creates no `ClusterRole`, `ClusterRoleBinding`, custom
  resource definition, or application RBAC.
- **K8S-03:** Every application Pod sets `automountServiceAccountToken: false`
  and uses no projected ServiceAccount token. A vetted evaluation subchart may
  instead use the chart's dedicated tokenless ServiceAccount only when rendered
  policy proves every such Pod selects that account and never overrides
  automounting to `true`.
- **K8S-04:** No workload uses host networking, host PID, host IPC, `hostPath`,
  privileged mode, `hostPort`, or unsafe sysctls.
- **K8S-05:** Every application container, init container, and Job satisfies the
  Kubernetes Restricted Pod Security Standard.
- **K8S-06:** Each application workload sets a fixed numeric user and group,
  `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, drops all Linux
  capabilities, and uses `seccompProfile.type: RuntimeDefault`.
- **K8S-07:** Application root filesystems are read-only. Writable storage is
  limited to documented `emptyDir` or persistent paths with size limits where
  supported.
- **K8S-08:** Default resource requests and conservative limits are present for
  every container. Operators may tune them without removing schema validation.

Compatibility overrides that weaken these controls are not part of the supported
profiles. A future override requires a separate security review, an explicit
warning, and a negative policy test proving it is not enabled by default.

### Image and artifact integrity

- **ART-01:** Every component supports independent image repository, tag, digest,
  pull policy, and pull Secret configuration.
- **ART-02:** A digest takes precedence over a tag. Release qualification and
  production examples use digests.
- **ART-03:** Release images contain the expected Hangar version, source revision,
  upstream revision, license, SBOM, and provenance metadata defined by the release
  policy.
- **ART-04:** The chart is published as an OCI artifact, its immutable digest is
  recorded, and the qualification workflow pulls and verifies that exact digest
  before installation.
- **ART-05:** Chart packages, images, attestations, and signatures are verified
  against the exact Hangar release workflow identity and GitHub OIDC issuer.
- **ART-06:** Third-party chart dependencies, CI actions, downloaded tools, and
  evaluation images are pinned and included in supply-chain review.
- **ART-07:** No rendered production workload references a Plane image,
  Plane-controlled endpoint, mutable `latest` tag, or unqualified image tag.

### Secret containment

- **SEC-01:** Both profiles reference pre-existing Kubernetes Secrets. Secret
  material is never accepted through ordinary Helm values.
- **SEC-02:** Secret references are split by trust boundary so a component receives
  only the keys it needs.
- **SEC-03:** Chart packages, values, rendered manifests, annotations, NOTES,
  tests, CI logs, and release assets contain no secret values or connection
  strings containing credentials.
- **SEC-04:** Stable Secret key mappings cover the Django `SECRET_KEY`, database,
  Valkey, RabbitMQ, object-storage, Live authentication, and optional identity or
  observability credentials discovered in the configuration inventory.
- **SEC-05:** Secret rotation procedures state which workloads restart and whether
  a credential can be overlapped safely.
- **SEC-06:** Documentation explains that Kubernetes Secrets require appropriate
  namespace RBAC and encryption at rest from the cluster operator.

Helm cannot safely prove that keys exist in a pre-existing Secret without reading
the Kubernetes API. The application workloads will not receive that permission.
The chart therefore validates Secret names and key mappings structurally, provides
an operator-run read-only preflight, and documents the resulting
`CreateContainerConfigError` diagnostics. It must not add an API-reading hook or
RBAC merely to improve this error message.

### Network isolation and SSRF defense

- **NET-01:** Default-deny ingress and egress policies are enabled in both
  profiles.
- **NET-02:** Ingress is limited to the configured ingress-controller namespace
  and Pod selectors. Selector labels are values because they are not portable
  across controllers.
- **NET-03:** DNS egress is limited to configured namespace and Pod selectors and
  TCP/UDP port 53.
- **NET-04:** Internal egress permits only the component flows in the reviewed
  communication matrix.
- **NET-05:** Public egress permits required ports while excluding IPv4 and IPv6
  private, loopback, link-local, metadata, multicast, carrier-grade NAT, and
  cluster ranges.
- **NET-06:** Operators must declare CIDRs for private databases, caches, queues,
  object storage, identity providers, webhooks, proxies, and observability
  collectors.
- **NET-07:** No database, queue, cache, object-storage console, health, or metrics
  endpoint is publicly exposed by default.
- **NET-08:** Network policy complements rather than replaces Hangar's DNS
  pinning, redirect validation, webhook allowlists, and other application-level
  SSRF controls.

Standard Kubernetes `NetworkPolicy` cannot express hostname allowlists and CNI
implementations differ in how `ipBlock` interacts with address translation. The
chart must document this limitation, test the supported CNIs, and provide examples
for optional FQDN-aware policies or a controlled egress proxy without requiring
either one.

### Privacy and startup safety

- **PRIV-01:** Telemetry and observability export are disabled by default.
- **PRIV-02:** No container startup, chart hook, CI job, or release process sends
  installation information to Plane or another third party.
- **PRIV-03:** Release discovery uses an explicitly configured Hangar-owned
  endpoint or remains disabled.
- **PRIV-04:** Instance identity is stable across pod restarts and replicas and is
  not derived from node, network-interface, CPU, memory, or filesystem details.
- **PRIV-05:** Startup initialization is idempotent and safe when multiple API pods
  begin concurrently.

## Helm chart interface

### Ownership, location, and versioning

The chart source will live at `charts/hangar`. It will be implemented from
Hangar's verified topology rather than copied from Plane's chart. Plane's chart
may be recorded as an architectural reference, but it is not a source baseline or
release dependency.

The package name is `hangar`. The chart version matches the Hangar product SemVer
without the leading `v`; `appVersion` contains the Hangar product version. For
example:

```yaml
version: 0.1.0-rc.4
appVersion: v0.1.0-rc.4
```

Chart versions are immutable and coupled to the release defined in
`docs/release-policy.md`. Correcting a published chart requires a new Hangar
prerelease or patch version.

### Public values surface

`values.schema.json` is part of the supported interface. Closed configuration
objects must set `additionalProperties: false`; intentionally extensible maps,
such as labels and annotations, must constrain their value types. Incompatible
combinations must fail before resources are submitted.

The interface will contain these groups:

```yaml
deploymentProfile: production

global:
  imagePullSecrets: []
  podLabels: {}
  podAnnotations: {}

api:
  image:
    repository: ghcr.io/szymczag/hangar-api
    tag: v0.1.0-rc.4
    digest: sha256:replace-with-release-digest
    pullPolicy: IfNotPresent
  replicas: 2
  resources: {}

ingress:
  enabled: true
  className: ""
  annotations: {}
  host: hangar.example.com
  tls:
    secretName: hangar-tls

existingSecrets:
  application:
    name: hangar-application
    keys:
      secretKey: SECRET_KEY
  live:
    name: hangar-live
    keys:
      liveServerSecretKey: LIVE_SERVER_SECRET_KEY
  database:
    name: hangar-database
    keys:
      url: DATABASE_URL
  cache:
    name: hangar-cache
    keys:
      url: REDIS_URL
  queue:
    name: hangar-queue
    keys:
      url: AMQP_URL
  objectStorage:
    name: hangar-object-storage
    keys:
      accessKeyId: AWS_ACCESS_KEY_ID
      secretAccessKey: AWS_SECRET_ACCESS_KEY

externalServices:
  objectStorage:
    endpoint: https://s3.example.com
    bucket: hangar
    region: eu-central-1
    tls:
      verify: true

networkPolicy:
  enabled: true
  ingressController:
    namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: ingress-nginx
    podSelector:
      matchLabels:
        app.kubernetes.io/name: ingress-nginx
  dns:
    namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: kube-system
    podSelector:
      matchLabels:
        k8s-app: kube-dns
  clusterCIDRs: []
  privateEgressCIDRs: []
  additionalEgress: []
```

This example defines the shape, not release-ready defaults. The implementation
must complete the configuration matrix before finalizing names, required fields,
and default resources.

Each component has its own `image`, `replicas`, `resources`, `podSecurityContext`,
`securityContext`, `nodeSelector`, `affinity`, `tolerations`,
`topologySpreadConstraints`, and disruption settings where applicable. Supported
security contexts expose only adjustments that preserve the Restricted standard.

The schema must enforce at least the following:

- `deploymentProfile` is exactly `production` or `evaluation`;
- production selects external services and cannot enable bundled dependencies;
- evaluation enables all required bundled dependencies and persistence;
- all application and evaluation dependency images include valid `sha256`
  digests in supported profile values;
- Secret names and required key mappings are non-empty;
- ingress requires a host and TLS Secret in production;
- ingress-controller and DNS selectors are non-empty;
- cluster CIDRs are declared before public egress is enabled;
- default-deny network policy cannot be disabled in supported profiles;
- replica counts and resource quantities are valid; and
- only AMD64 scheduling is allowed until multi-architecture images are qualified.

Arbitrary `extraEnv`, additional containers, init containers, host aliases, raw
manifests, or unstructured pod-spec injection are outside the initial supported
interface. They make validation and least-privilege guarantees ineffective.

### Configuration ownership

Phase 0 produces a configuration matrix containing every runtime and build-time
variable used by API, worker, beat, Live, web, admin, and space. Each row records:

- owning component and consumer workloads;
- public, sensitive, or release-generated classification;
- source: chart value, Secret key, image metadata, or derived value;
- required/defaulted/optional status;
- validation and redaction behavior;
- whether a change requires a rollout or image rebuild; and
- the production and evaluation defaults.

The inventory must include privacy, telemetry, release discovery, CORS, CSRF,
trusted proxies, SSO/OAuth, SMTP, SSRF and webhook exceptions, upload limits,
object storage, retention, rate limits, and observability settings. A variable is
not supported merely because it appears in a Compose environment file.

### Migration and startup ordering

The migration is a normal, revision-scoped Job rather than a pre-install Helm
hook. A pre-install hook cannot depend on evaluation services that are created in
the same release. The Job name includes the Helm release revision, and old Jobs
are removed with a tested TTL and history policy.

API, worker, and beat workloads wait for the migration state with bounded
timeouts. The migration Job has an `activeDeadlineSeconds`, a small
`backoffLimit`, a bounded database-connectivity wait before migration execution,
structured logs, and no automatic database downgrade behavior. The wait parses
`DATABASE_URL` without logging it and checks only the configured host and port;
it requires no service-account token or additional image.
Helm installation and upgrade instructions use `--wait --wait-for-jobs` with an
explicit timeout.

Migration commands must be idempotent under retry. A Helm rollback does not imply
a database rollback: release notes and the operator runbook must state whether the
previous application can run against the migrated schema or whether a coordinated
database restore is required.

## Implementation and qualification workstreams

Each phase is independently reviewable. A later phase must not hide an unmet gate
from an earlier phase.

### Phase 0: architecture, compatibility, and threat model

1. Record the component and dependency data flows, trust boundaries, ports, and
   public routes.
2. Complete the configuration and Secret matrix.
3. Select and record supported Kubernetes, Helm, ingress-controller, and CNI
   versions from versions still maintained when implementation begins.
4. Select vetted evaluation subcharts, record their licenses and maintainers, pin
   versions in `Chart.lock`, and document replacement criteria.
5. Define PostgreSQL, Valkey, RabbitMQ, and object-storage compatibility ranges.
6. Threat-model ingress, WebSockets, uploads, OAuth/SSO callbacks, webhooks,
   outbound fetches, migrations, chart values, dependencies, CI, registry
   publication, and compromised cluster tenants.
7. Define availability assumptions, support boundaries, and the minimum upgrade
   source version.

Gate: the architecture, configuration matrix, threat model, compatibility policy,
dependency selection, and support boundaries receive maintainer and security
review.

### Phase 1: runtime image and startup hardening

1. Assign a fixed numeric UID and GID to every runtime image.
2. Replace world-writable paths with minimum ownership and permissions.
3. Make application code and dependencies immutable after build.
4. Reconfigure Nginx PID, cache, and temporary paths for non-root operation.
5. Identify and mount only the required writable paths for API, workers, Live,
   space, and `/tmp`.
6. Remove runtime compilers, package managers, and unnecessary diagnostic tools
   where feasible.
7. Remove pod-hardware-derived identity and make initialization concurrency-safe.
8. Remove the Plane release lookup and prove that telemetry/export is disabled by
   default.
9. Add bounded dependency and migration waits with useful failure messages.
10. Add dedicated health endpoints or safe probe commands for every component.
11. Prove same-origin frontend configuration or implement safe runtime config.
12. Test final images with the exact Restricted security context and read-only
    filesystem used by the chart.

Gate: every application image starts, passes probes, terminates cleanly, and
satisfies K8S-05 through K8S-08 and PRIV-01 through PRIV-05.

### Phase 2: core chart and public interface

1. Create `Chart.yaml`, `Chart.lock`, `values.yaml`, `values.schema.json`, helper
   templates, NOTES, tests, and profile examples under `charts/hangar`.
2. Implement Hangar naming, recommended labels, ownership annotations, and
   deterministic resource names.
3. Add all application Deployments, Services, the revision-scoped migration Job,
   ConfigMaps, Ingress, and disruption controls.
4. Implement independent image references with digest precedence.
5. Add AMD64 scheduling defaults while releases are AMD64-only.
6. Use configuration checksums to roll workloads without copying Secret content
   into annotations.
7. Implement production external-service configuration and evaluation
   dependencies with persistent storage.
8. Reject unsupported profile combinations through the schema.

Gate: both profiles lint and render deterministically; production renders only
external services; all resources are namespaced; and no output contains a Plane
image or endpoint.

### Phase 3: Secrets and configuration

1. Implement the reviewed Secret groups and per-component key projections.
2. Ensure API, worker, beat, migrator, and Live receive only required keys.
3. Add structural validation for Secret references without Kubernetes API RBAC.
4. Add operator preflight and rotation procedures.
5. Test all Hangar-specific privacy, release, CORS, CSRF, proxy, SSO, SSRF,
   webhook, upload, retention, and observability settings.
6. Scan rendered output, Helm debug logs, tests, and release assets for secret
   material.
7. Document optional integrations with External Secrets Operator, SOPS/Flux,
   Sealed Secrets, and cloud workload identity without making them dependencies.

Gate: SEC-01 through SEC-06 pass, no release input contains production secret
values, and missing or rotated keys have tested operator-visible behavior.

### Phase 4: ingress and network hardening

1. Implement all request routes and canonical redirects.
2. Verify HTTPS redirects, trusted forwarding headers, request limits, CORS/CSRF,
   OAuth callbacks, static content, and WebSocket upgrades.
3. Add default-deny ingress and egress policies.
4. Permit only the reviewed internal communication matrix.
5. Implement configurable ingress-controller and DNS selectors.
6. Implement IPv4 and IPv6 public-egress exclusions and private CIDR exceptions.
7. Keep evaluation dependency management endpoints private.
8. Test at least the default CI CNI and document any controller or CNI-specific
   behavior included in the support matrix.

Gate: every required flow succeeds, prohibited lateral and private-destination
flows fail, public routes work behind HTTPS, and NET-01 through NET-08 pass.

### Phase 5: availability and lifecycle operations

1. Establish measured default requests and limits for each component and
   evaluation dependency.
2. Add graceful termination and WebSocket draining; verify Celery work is not
   silently lost during ordinary rollouts.
3. Add PodDisruptionBudgets only where replica count and component semantics make
   them safe.
4. Add topology spreading and anti-affinity recommendations.
5. Keep horizontal autoscaling opt-in until component-specific signals and
   scaling limits are tested.
6. Document external-service TLS verification, connection limits, timeouts, and
   credential rotation.
7. Define a coordinated PostgreSQL and uploaded-object backup point. State which
   Valkey and RabbitMQ state is required for recovery.
8. Test clean installation, upgrade from the minimum supported version, migration
   failure, retry, rollback decision, and restoration into a clean namespace.
9. Test evaluation persistence through pod and node replacement and document its
   single-instance limitations.
10. Verify uninstall behavior and persistent-volume retention.

Gate: both profiles install cleanly; upgrade and failure paths are understood; a
database and object restore succeeds; and the runbook contains no undocumented
recovery step.

### Phase 6: CI and policy enforcement

CI must not possess credentials for a production or user-managed Kubernetes
cluster.

1. Run Helm linting and strict schema validation.
2. Run chart unit tests for helpers, profiles, routes, security contexts, and
   conditional resources.
3. Render supported profiles and representative option combinations twice and
   compare normalized output for determinism.
4. Validate rendered resources against every supported Kubernetes API version.
5. Enforce repository-owned policy checks rejecting root containers, privilege
   escalation, added capabilities, token mounts, cluster-scoped resources, host
   access, mutable production images, missing resources/probes, and public
   internal Services.
6. Scan charts, dependencies, rendered manifests, and evaluation images.
7. Install both profiles in ephemeral clusters whose namespace enforces
   Restricted Pod Security.
8. Exercise migrations, readiness, authentication, routing, uploads, background
   jobs, Live/WebSockets, network allow/deny cases, upgrade, restore, and uninstall.
9. Pin third-party actions by full commit SHA. Pin downloaded tools by version and
   verify checksums before execution.
10. Upload sanitized renders, policy reports, test results, and image manifests as
    qualification evidence.

The concrete toolchain should use pinned releases of Helm, chart-testing or an
equivalent chart linter, kubeconform or an equivalent schema validator,
repository-owned Rego/policy tests, an ephemeral Kubernetes distribution, and an
image/chart scanner. Exact tool choices and versions are recorded in Phase 0.

Gate: static validation, policy enforcement, both ephemeral installations, and
all end-to-end scenarios pass without a long-lived credential.

#### Implemented ephemeral evaluation harness

`charts/hangar/tests/e2e-kind.sh` is the first live qualification layer. It uses
only the GitHub-hosted runner's Docker daemon and a job-scoped package token; it
does not accept or load a kubeconfig for an external cluster. The cluster name is
unique to the run, the API context is written to a mode-restricted temporary
directory, diagnostics are collected on failure, and the cluster and generated
credentials are destroyed on exit.

The qualification stack is deliberately versioned independently from Hangar:

| Layer                    | Qualification pin                                                                                                            |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| Kind client              | `v0.32.0`, downloaded for the runner architecture and verified against a repository-owned SHA-256 pin                        |
| Kubernetes node          | `kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5`                               |
| Kubernetes schema/client | Kubernetes 1.36.2 schemas and `kubectl v1.36.2`; kubectl is verified against repository-owned SHA-256 pins                   |
| Helm                     | `v4.2.0`, installed by a full-commit-pinned GitHub Action                                                                    |
| CNI and policy engine    | Cilium `1.19.5`; OCI chart digest `sha256:557ea3b67b2380bdf91f3006ecea924e10e2963dbaf6085887652311e581460b`                  |
| Ingress controller       | F5 NGINX `5.5.1`; Helm chart `2.6.1` at OCI digest `sha256:fe6899d4087de3cdd809b5928b7373b0a97a58312f40733938dda84f4d571516` |
| Ingress controller image | AMD64 image digest `sha256:0e23c34b1095aefb87d720d99a82528999cc93e53e74c0edd6339dba70d473bf`                                 |

The qualification values use F5 NGINX's `nginx.org/ssl-redirect` and
`nginx.org/websocket-services` annotations. The chart remains
controller-neutral; operators configure equivalent HTTPS redirect and
WebSocket forwarding behavior for their chosen ingress implementation.

The harness refuses source-chart placeholder application digests. It creates a
Restricted Pod Security namespace, generated non-default credentials, a
short-lived self-signed test certificate, and four static retained volumes. The
static volumes use a no-provisioner `StorageClass` so the test does not mistake a
dynamic provisioner's behavior for chart behavior. `hostPath` exists only in
these cluster-owned test fixtures; rendered Hangar workloads remain subject to
the repository policy that forbids host access.

The evaluation profile schema-locks RabbitMQ 4.x's
`deprecated_features.permit.transient_nonexcl_queues` compatibility permission.
The current Celery/Kombu stack still declares this queue type; the permission is
limited to the bundled broker and must be retired after the application
dependency is upgraded. Qualification checks controller rollouts explicitly so
completed migration Job Pods are not incorrectly expected to remain Ready.

The live assertions currently cover:

- evaluation installation with failed resources retained for diagnostics and
  completion of revision-scoped migrations;
- readiness of all release workloads and binding of every dependency PVC;
- TLS routing for Web, Admin, Space, API, and Live, HTTP-to-HTTPS redirect, and a
  real WebSocket `101 Switching Protocols` response;
- positive dependency flows plus negative API-lateral and link-local metadata
  flows under Cilium-enforced `NetworkPolicy`;
- object-store data surviving StatefulSet pod recreation;
- an atomic Helm upgrade and its new migration Job; and
- Helm uninstall retaining all four evaluation PVCs.

The release workflow resolves application manifest digests, packages a candidate
chart, and installs that exact archive. Attestation, signing, and publication
cannot begin until the archive passes. A separate manual `Qualify Hangar Helm
Chart` workflow can repeat the same test against an existing release or preview
image tag. Preview runs use a unique synthetic chart version while retaining the
resolved preview image digests. The container publication workflow can also
invoke this reusable qualification workflow through its `run_helm_e2e` input,
which permits end-to-end branch qualification before the standalone workflow is
present on the default branch. A guarded `reuse_preview_images` input skips
container publication for qualification-only retries; the E2E workflow still
resolves every existing preview tag to an immutable digest before installation.
The next CI expansion is the production profile
with disposable external services, followed by authenticated uploads,
background jobs, migration-failure recovery, and coordinated restore scenarios.

### Phase 7: OCI publication and release integration

The chart will be published at:

```text
oci://ghcr.io/szymczag/charts/hangar
```

1. Build, attest, sign, and verify all release images before packaging the chart.
2. Resolve the exact application and evaluation image digests and generate the
   qualification values from them.
3. Test the packaged chart against those exact digests.
4. Package the chart with the Hangar release SemVer and matching `appVersion`.
5. Publish the chart to GHCR using the job-scoped `GITHUB_TOKEN`.
6. Record the OCI digest, generate the archive checksum, and sign the OCI digest
   keylessly through GitHub OIDC.
7. Verify the chart and images against the exact workflow identity, namespaced
   release tag, and expected issuer.
8. Create GitHub artifact attestations and attach the chart archive, checksums,
   image/dependency digest manifest, sanitized qualification values, and
   verification instructions to the GitHub Release.
9. Pull the public chart by digest with a pinned OCI-compatible client, verify the
   resulting package, and install that package in a fresh ephemeral cluster. Pull
   every referenced image anonymously by digest as part of the same exercise.
10. Reject reuse of an existing chart version, tag, digest record, or release
    asset name.

Workflow permissions remain job-local:

| Job                              | Required permissions                                                                                 |
| -------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Validation and qualification     | `contents: read`                                                                                     |
| Chart publication                | `contents: read`, `packages: write`                                                                  |
| Keyless signing and attestations | publication permissions plus `id-token: write` and only the attestation permission actually required |
| GitHub Release                   | `contents: write` and only other permissions demonstrably required                                   |

No publication job receives a kubeconfig or other user-cluster credential.

Gate: public artifacts are immutable and anonymously pullable; digests,
checksums, attestations, and signatures verify; and installation from the
published chart digest succeeds.

### Phase 8: operator documentation and inherited-path retirement

The initial task-oriented operator documentation is now organized under
`docs/kubernetes/`:

- [documentation landing page](kubernetes/README.md);
- [evaluation installation](kubernetes/evaluation-install.md);
- [production-profile preparation](kubernetes/production-install.md);
- [configuration reference](kubernetes/configuration.md);
- [operations](kubernetes/operations.md);
- [security and artifact verification](kubernetes/security.md); and
- [troubleshooting](kubernetes/troubleshooting.md).

These guides cover:

- production prerequisites and installation;
- evaluation installation and limitations;
- Secret creation, preflight, and rotation;
- ingress, DNS, certificates, and trusted proxies;
- NetworkPolicy behavior and private-destination exceptions;
- resource sizing, replicas, disruption, and scaling;
- backup and restore;
- upgrade, migration failure, and rollback decisions;
- OCI digest, checksum, attestation, and signature verification;
- future air-gapped mirroring and installation; and
- troubleshooting and support-bundle collection without credentials.

Update the main README only after the tested path exists. At that point, replace
the Plane Kubernetes link with Hangar documentation. Remove or explicitly disable
the inherited Plane feature-deployment workflow in a visible, independently
reviewed change.

Gate: a maintainer can start with an empty namespace, install either profile,
verify its artifacts, operate it, complete an upgrade and backup/restore exercise,
and make the documented rollback decision without an undocumented step.

## Proposed pull-request sequence

1. **Architecture and compatibility:** configuration matrix, threat model,
   support matrix, dependency selection, and requirement traceability.
2. **Runtime hardening:** non-root images, immutable filesystems, stable startup,
   privacy controls, probes, and bounded waits.
3. **Production chart:** external services, values schema, application workloads,
   migration ordering, and basic install tests.
4. **Evaluation profile:** pinned dependency subcharts, persistence, credentials,
   and recovery limitations.
5. **Security controls:** Secret projections, Restricted contexts, ingress, and
   default-deny NetworkPolicies.
6. **Lifecycle qualification:** resources, disruption, upgrades, backup/restore,
   rollback decisions, and ephemeral-cluster tests.
7. **Publication:** OCI packaging, release coupling, digest manifests,
   attestations, Cosign signing, and public verification.
8. **Documentation and cleanup:** operator guides, README correction, and removal
   of inherited deployment paths.

Each pull request must list the requirement identifiers it addresses and link the
evidence that proves them. A partial phase must not be represented as supported
Kubernetes functionality.

## Required test scenarios

### Rendering and policy

- Valid production and evaluation renders are deterministic.
- Invalid profiles, mixed external/bundled services, missing Secret references,
  invalid digests, and unsupported architectures fail schema validation.
- Rendered production output contains no bundled stateful service, Plane image,
  Plane endpoint, mutable image, cluster-scoped resource, or secret value.
- Every Pod, init container, and Job passes Restricted Pod Security and the
  repository policy suite.

### Application and ingress

- Every route in the request-routing contract reaches only its intended Service.
- HTTPS redirects and forwarded scheme/host handling produce correct public URLs.
- CORS, CSRF, and OAuth/SSO callback behavior use the configured public origin.
- Requests over the upload limit fail safely; valid upload and download flows
  succeed.
- Live HTTP and WebSocket sessions connect, remain healthy, and drain during a
  rollout.
- Frontend images work on a new host without rebuilding.

### Secrets and networks

- Missing and rotated Secret keys fail or recover as documented without printing
  their values.
- Required DNS, database, cache, queue, object-storage, API, and Live flows pass.
- Metadata, loopback, private ranges, prohibited lateral traffic, and undeclared
  integration destinations fail.
- Explicit private CIDR exceptions enable only the intended destination and port.
- Evaluation management consoles remain unreachable through ingress.

### Lifecycle and recovery

- Clean production and evaluation installations succeed with
  `--wait --wait-for-jobs`.
- Dependency delay, migration failure, deadline, retry, and subsequent recovery
  produce an actionable Helm result.
- Upgrade from the minimum supported version preserves representative users,
  projects, authentication, uploads, and background work.
- The documented rollback decision is correct for both compatible and
  incompatible database migrations.
- A coordinated PostgreSQL and uploaded-object backup restores into a clean
  namespace and passes application smoke tests.
- Evaluation data survives pod recreation; uninstall retains persistent data by
  default and the documented cleanup removes it deliberately.

### Release artifacts

- Chart and image digests, checksums, SBOMs, provenance, attestations, and keyless
  signatures verify against the expected release identity.
- Public artifacts can be pulled anonymously.
- Installation from the package pulled and verified by published chart digest
  uses the recorded image digests and reproduces the qualified deployment.
- Reusing a published chart version or release asset is rejected.

## Release qualification checklist

A Kubernetes-capable Hangar release is supported only when the evidence record
links every checked item to a CI run, report, digest, or signed manual exercise.

- [ ] Phase 0 architecture, threat model, compatibility, and dependency reviews
      are approved.
- [ ] K8S-01 through K8S-08 pass for every rendered workload.
- [ ] ART-01 through ART-07 pass for the packaged chart and all images.
- [ ] SEC-01 through SEC-06 pass, including redaction and rotation exercises.
- [ ] NET-01 through NET-08 pass positive and negative connectivity tests.
- [ ] PRIV-01 through PRIV-05 pass startup and privacy tests.
- [ ] Production installs with external PostgreSQL, Valkey, RabbitMQ, and object
      storage.
- [x] Evaluation installs with pinned dependencies, non-default credentials, and
      persistent storage.
- [ ] HTTPS ingress, routing, trusted headers, WebSockets, uploads, and limits are
      verified.
- [ ] Migrations, workers, beat, retries, timeouts, and graceful shutdown are
      verified.
- [ ] Upgrade from the minimum supported version succeeds.
- [ ] Backup and restore of PostgreSQL and uploaded objects succeeds in a clean
      namespace.
- [ ] Rollback compatibility and database-restore requirements are documented for
      the release.
- [ ] The OCI chart and all image/dependency digests match the evidence manifest.
- [x] Checksums, provenance, attestations, and keyless signatures verify in
      publication run 29278653303.
- [ ] Public chart and image digest pulls and installation of the verified chart
      package succeed.
- [ ] Operator documentation reproduces the qualified process.
- [x] The README no longer directs users to Plane's Kubernetes deployment.
- [x] The inherited feature-deployment workflow is removed or disabled.

## Principal risks and responses

| Risk                                                         | Required response                                                                          |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| Runtime images require root or writable application code     | Fix the images; do not weaken the chart security context                                   |
| Frontend URLs are fixed at build time                        | Prove same-origin behavior or add safe runtime configuration before release                |
| API startup performs external or replica-unsafe side effects | Remove external Plane calls and make initialization stable and idempotent                  |
| Evaluation subcharts or images change independently          | Pin charts, lock dependencies, record image digests, scan, and define replacement criteria |
| Default-deny egress breaks private integrations              | Require explicit CIDR/port exceptions and provide tested diagnostics                       |
| NetworkPolicy behavior varies by CNI                         | Publish a tested support matrix and document non-portable behavior                         |
| Migration succeeds but application rollout fails             | Require pre-upgrade backup and release-specific rollback compatibility guidance            |
| Helm rollback is mistaken for database rollback              | State explicitly when restore is required and test that decision                           |
| Secrets leak through values or debug artifacts               | Accept references only, project minimum keys, redact, and scan evidence                    |
| Signing identity is too broad                                | Verify the exact workflow, tag reference, issuer, and immutable digest                     |
| Evaluation is mistaken for production HA                     | Label it consistently and exclude HA claims from its support statement                     |

## References

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/)
- [Kubernetes RBAC good practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/)
- [Good practices for Kubernetes Secrets](https://kubernetes.io/docs/concepts/security/secrets-good-practices/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Helm OCI registries](https://helm.sh/docs/v3/topics/registries/)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Hangar release and versioning policy](release-policy.md)
