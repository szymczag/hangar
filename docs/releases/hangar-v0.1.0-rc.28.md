## Security and privacy

`rc.28` hardens the Todoist import review and admission boundary. The execute
endpoint now requires a short-lived, server-signed preview grant bound to the
administrator, workspace, destination project, and exact uploaded source. Each
grant carries a random nonce that can reserve at most one job, so missing,
expired, altered, cross-scope, and replayed grants fail closed before source
retention or dispatch.

Import reservation now locks the destination project and rechecks both active
jobs and completed duplicates inside the reservation transaction. This closes a
race in which a concurrent import could complete between the earlier request
check and reservation, bypassing the explicit duplicate confirmation.

The controls were validated with regression tests for mandatory preview,
actor/project/source binding, expiration, single use, and transactional duplicate
admission. Publication remains gated on the full API and Todoist suites, security
migrations, frontend checks, release metadata, Helm policy tests, CodeQL,
artifact attestations, and keyless signatures.

## Migrations and compatibility

Migration `ext.0011_import_job_preview_nonce` adds a nullable unique UUID field
to import jobs. Existing jobs remain valid and require no data backfill. New jobs
created through the HTTP Todoist importer consume the nonce from their signed
preview grant; trusted internal reservation callers receive a generated nonce.

There is no new Helm value, Secret, Kubernetes resource, public route, storage,
RBAC, or NetworkPolicy change. Existing `rc.27` values and deployment
configuration remain structurally compatible. The preview grant lifetime
defaults to 900 seconds and requires no operator action.

Deploy all application images as one Helm revision and wait for the
revision-scoped migration Job before admitting traffic. The web and API request
contract changed together: an `rc.28` web client sends the signed grant, while
the `rc.28` API no longer accepts a client-calculated digest as proof of preview.
Do not operate mixed `rc.27` and `rc.28` web/API revisions.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.28`, the chart version is
`0.1.0-rc.28`, the signed Git tag is `hangar-v0.1.0-rc.28`, and the OCI
chart reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.28`.
`rc.27` is the immediately previous complete publication. `rc.1`, `rc.2`,
`rc.20`, `rc.24`, and `rc.25` were consumed by incomplete publication attempts
and are not upgrade or rollback targets. `rc.24` and `rc.25` each published only
a subset of their containers and no chart or GitHub Release.

## Known limitations and rollback

Hangar `rc.28` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

`rc.27` is structurally compatible as an emergency technical rollback target;
the nullable preview-nonce column can remain in place. Rolling back restores the
superseded Todoist admission behavior, so there is no security-equivalent
rollback target. Prefer a forward correction; if availability recovery requires
rollback, move every application component together, temporarily disable Todoist
imports, and return to `rc.28` promptly. Restore a database backup only when
unrelated writes, corruption, or the incident requires point-in-time recovery.
