## Security and privacy

`rc.25` ports the applicable upstream authorization and IDOR hardening reviewed
after `rc.23`. It closes cross-scope access paths where an authenticated caller
with a valid identifier could reach data outside the workspace, project, issue,
membership, ownership, or nested-object boundary carried by the request.

The protected surfaces include issue comments, attachments, activity, relations,
sub-issues, member preferences, project invitations, draft conversion, state
updates, deploy-board objects, Spaces board and intake objects, and external API
issue comments and attachments. Restricted guests can no longer use issue
subresource endpoints to bypass issue visibility. Workspace administrators retain
their administrative visibility even when their project membership has a lower
role, and guest-visible history continues to exclude confidential worklog events.

The release also rejects mass assignment of project audit fields and workspace
membership identity fields, scopes webhook HMAC secrets to the correct workspace,
requires administrator authority for state partial updates, adds a page-ordering
allowlist, and caps grouped pagination inputs. Where an upstream patch overlapped
Hangar-specific controls, the port preserves Hangar's stricter upload, SSRF,
sub-issue transaction and cycle, workspace-administrator, and full-PUT behavior.

Publication is gated on the full API suite, authorization contract tests,
security migrations, lint, release metadata, Helm rendering and schema policies,
copyright checks, and CodeQL.

## Migrations and compatibility

There is no new Django database migration, Helm value, Secret, Kubernetes
resource, public route, storage, RBAC, or NetworkPolicy change in this release.
Existing `rc.23` values and deployment configuration remain structurally
compatible, and no operator configuration action is required.

Deploy the API, migrator, workers, Spaces, and web applications as one Helm
revision so all callers and authorization boundaries move together. The normal
revision-scoped migration Job must still complete before application traffic is
admitted even though it has no new schema operation to apply.

The inherited Plane source remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.25`, the chart version is
`0.1.0-rc.25`, the signed Git tag is `hangar-v0.1.0-rc.25`, and the OCI
chart reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.25`.
`rc.23` is the immediately previous complete publication. `rc.1`, `rc.2`,
`rc.20`, and `rc.24` were consumed by incomplete publication attempts and are
not upgrade or rollback targets. `rc.24` published only a subset of its
containers and no chart or GitHub Release.

## Known limitations and rollback

Hangar `rc.25` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Authorization checks reduce exposure only when membership and role records are
accurate and inactive memberships are revoked promptly. Operators should still
apply least privilege, protect identifiers and logs, monitor denied requests, and
keep public ingress limited to documented routes.

There is no security-equivalent rollback target. Rolling back to `rc.23`
restores the corrected Django 5.2.16 runtime but removes the authorization and
object-scope fixes shipped here. No database or configuration conversion blocks a
technical rollback, but an emergency rollback should restrict the affected API
surfaces and return every application component to `rc.25` as soon as possible.
Restore a database backup only when unrelated writes, corruption, or the incident
requires point-in-time recovery.
