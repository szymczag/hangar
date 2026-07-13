## Security and privacy

This release candidate introduces the Hangar-owned Helm chart with Restricted
Pod Security-compatible application workloads, fixed non-root identities,
read-only root filesystems, dropped Linux capabilities, seccomp profiles, and
disabled service-account token mounting. Application credentials must be supplied
through pre-existing Kubernetes Secrets; the chart does not generate credentials
or copy Secret values into ConfigMaps or Helm values.

Default-deny NetworkPolicies limit ingress and workload-to-workload traffic.
Private, link-local, and cloud metadata destinations are denied unless an operator
adds a narrowly scoped production egress rule. Telemetry and release discovery
remain disabled by default.

The release workflow resolves application images to immutable digests, qualifies
the packaged chart against those digests, creates build-provenance attestations,
and signs and verifies the published OCI chart through GitHub OIDC. The evaluation
profile passed the complete AMD64 ephemeral-cluster suite, including HTTPS,
WebSockets, Cilium policy enforcement, migrations, persistence, upgrade, uninstall,
and retained-volume checks.

Production security qualification is not complete. This release candidate must not
be treated as a supported production deployment.

## Migrations and compatibility

Installations and upgrades run a revision-scoped migration Job before application
rollout completes. The Job waits for PostgreSQL with a bounded deadline and receives
only the application, database, and cache configuration needed to load Django and
run migrations. Operators must use `--wait-for-jobs`, inspect migration logs, and
take a coordinated PostgreSQL and object-storage backup before every upgrade.

The chart declares Kubernetes 1.30 through 1.35 compatibility. Helm 4.2 is the
qualified client, and the published application and bundled evaluation dependency
images are AMD64-only. The bundled evaluation profile is intended for a new,
dedicated namespace and does not define a supported in-place migration from the
upstream `plane-ce` chart. Existing Plane chart values are not automatically
translated to Hangar values.

The production profile renders external PostgreSQL, Valkey, RabbitMQ, and
S3-compatible service configuration, but those combinations have not completed the
release support matrix. Operators evaluating that profile must independently verify
service versions, TLS, authentication, backup, and application compatibility.

## Known limitations and rollback

Only the evaluation profile has completed live cluster qualification. It uses
single-replica bundled stateful services and is suitable for non-critical testing,
not high availability or production. Production installation, authenticated upload
and background-task flows, coordinated backup and restore, migration-failure
recovery, vulnerability and license review, public-distribution verification, and
the supported Kubernetes version matrix remain open qualification gates.

The qualified ingress path used F5 NGINX and the policy checks used Cilium. The
chart is controller-neutral, so operators selecting other ingress controllers or
CNIs must supply equivalent HTTPS redirect, WebSocket, and NetworkPolicy behavior.

`--rollback-on-failure` restores Kubernetes workload revisions but does not reverse
database migrations or external-service changes. If an upgrade applies an
incompatible migration, recover PostgreSQL and object storage from the coordinated
pre-upgrade backup instead of relying on Helm rollback. Evaluation PVCs are retained
after uninstall and must be reviewed and deleted explicitly when their data is no
longer required.
