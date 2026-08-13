## Security and privacy

`rc.27` updates vulnerable transitive and direct JavaScript dependencies to
patched releases: `nanoid` 3.3.17, `js-yaml` 4.3.1, `undici` 7.29.0,
`fast-uri` 3.1.5, `postcss` 8.5.25, and `brace-expansion` 5.0.9. The production
dependency audit reports no known vulnerabilities at high or critical severity.

The release also ports five applicable fixes reviewed from Plane 1.4.1. Workspace
module member updates now handle absent member lists safely, notification reads
use the canonical API route, layout and dropdown rendering tolerate incomplete
state, project and workspace lookups are guarded against missing data, and the web
application performs one bounded automatic reload when a deployment leaves an
open tab referring to a stale frontend asset. The reload marker is Hangar-scoped
and prevents an endless refresh loop.

These changes do not widen the existing upload, outbound-request, authorization,
or Kubernetes network boundaries. Publication remains gated on dependency audit,
the full API suite, frontend contract tests, lint and type checks, release
metadata, Helm rendering and schema policies, CodeQL, artifact attestations, and
keyless signatures.

## Migrations and compatibility

There is no new Django database migration, Helm value, Secret, Kubernetes
resource, public route, storage, RBAC, or NetworkPolicy change in this release.
Existing `rc.26` values and deployment configuration remain structurally
compatible, and no operator configuration action is required.

Deploy all application images as one Helm revision. The normal revision-scoped
migration Job must still complete before application traffic is admitted even
though it has no new schema operation to apply.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`; the
Plane 1.4.1 fixes above are selective backports rather than a baseline transition.
The qualification boundary remains Kubernetes 1.30 through 1.36 (including
1.36.2), Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress
with WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.27`, the chart version is
`0.1.0-rc.27`, the signed Git tag is `hangar-v0.1.0-rc.27`, and the OCI
chart reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.27`.
`rc.26` is the immediately previous complete publication. `rc.1`, `rc.2`,
`rc.20`, `rc.24`, and `rc.25` were consumed by incomplete publication attempts
and are not upgrade or rollback targets. `rc.24` and `rc.25` each published only
a subset of their containers and no chart or GitHub Release.

## Known limitations and rollback

Hangar `rc.27` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

`rc.26` is structurally compatible as an emergency technical rollback target,
but it restores the superseded dependency versions and removes the operational
fixes shipped here. There is therefore no security-equivalent rollback target.
Prefer a forward correction; if availability recovery requires rollback, move
every application component together and return to `rc.27` promptly. Restore a
database backup only when unrelated writes, corruption, or the incident requires
point-in-time recovery.
