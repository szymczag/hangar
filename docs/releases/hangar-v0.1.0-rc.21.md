## Security and privacy

`rc.21` publishes the reviewed Plane v1.4.0 final sync and the application
hardening prepared for the incomplete `rc.20` attempt. Saved and advanced
analytics now remain within the requesting user's active workspace and project
memberships. Workspace search, cycle and module mutation, and project
deploy-board routes apply consistent active-membership, role, and entity-type
boundaries to list, detail, and update paths.

GitHub, GitLab, and Gitea OAuth flows issue a cryptographically random,
session-bound transaction state. It is provider-specific,
application-versus-space-specific, expires after ten minutes, and is consumed
on the first callback attempt. Missing, replayed, stale, cross-provider, and
cross-surface callbacks fail closed. Authorization codes and provider tokens
are not added to logs.

Gitea OAuth, OIDC, and SMTP outbound connections validate resolved destinations
against Hangar's blocked-address policy and pin the selected address. Gitea
requires an HTTPS origin in production, refuses redirects, limits response
bodies, and ignores ambient proxy routing. OIDC bodies are bounded and
transition-address encodings remain blocked. SMTP restricts ports, verifies the
connected peer and TLS hostname, and refuses to send credentials without TLS.

Live PDF export validates workspace slugs and canonical UUIDs, limits each
document to 50 unique image assets, accepts only credential-free HTTP(S)
presigned URLs, refuses redirects, bounds request time and streamed response
size, and embeds only approved raster media types.

The release-note generator remains fail-closed for non-linear upstream history.
`rc.21` adds a release-specific maintainer-review record containing the exact
previous and current Hangar tags, upstream repository, and upstream revisions.
The generator accepts the transition only when every field matches repository
history. It links the two immutable commits separately instead of presenting an
ambiguous automatically generated comparison. Malformed, duplicated, stale,
wrong-repository, wrong-tag, or mismatched review records are rejected before
container builds begin.

The application review covered changed authentication and authorization
boundaries, outbound request sinks, and upload-adjacent asset processing.
Focused regression tests cover corrected object scopes, OAuth transaction
lifecycle, Gitea and SMTP destination policies, PDF asset limits, and both
accepted and rejected upstream-transition reviews. Complete API, migration,
frontend, lint, chart, CodeQL, copyright, signing, and publication checks remain
required.

## Migrations and compatibility

`rc.21` updates the inherited Plane source from `v1.4.0-rc2` to final `v1.4.0`
and adopts Django 5.2.15 plus the final upstream dependency, filtering, avatar,
and application fixes.

The release adds Django migration
`0129_alter_draftissue_assignees_alter_issue_assignees_and_more`. It records the
final relationship metadata for draft issue assignees, issue assignees, and
module members and does not rewrite existing issue or membership rows. The Helm
migration Job must complete before application traffic is admitted. Do not run
a mixture of `rc.19` and `rc.21` API, worker, Live, or frontend images.

Existing `rc.19` Helm values and Secret names remain structurally compatible.
There is no Helm resource, RBAC, NetworkPolicy, storage, or public-route contract
change. Operators using private Gitea or SMTP destinations must review the new
environment-owned allowlists and ensure the same narrow destinations are
admitted by `networkPolicy.privateEgress`. Those environment allowlists are not
exposed as supported chart values in this release; public-only deployments need
no new value.

OAuth transactions begun before deployment cannot be resumed and users must
restart sign-in. Existing federated identity bindings, uploaded assets,
projects, issues, and mail configuration are not rewritten.

The qualified boundary remains Kubernetes 1.30 through 1.36, including 1.36.2,
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.21`, the chart version is
`0.1.0-rc.21`, the signed Git tag is `hangar-v0.1.0-rc.21`, and the OCI
chart reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.21`.
`rc.19` is the immediately previous complete publication. `rc.20` was consumed
by an incomplete publication attempt and is not an upgrade or rollback target.

## Known limitations and rollback

Hangar `rc.21` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

The chart does not provide supported values for private Gitea or SMTP
destination allowlists. Do not patch generated Deployments to weaken the
application boundary; keep those integrations disabled or use public endpoints
until the chart exposes a reviewed configuration contract. Accepted PDF raster
images are bounded and type-checked, but this is not malware detection or a
content-disarm service.

There is no security-equivalent rollback target among earlier release
candidates. Rolling back to `rc.19` restores the authorization, OAuth
transaction, outbound-destination, and PDF-fetching weaknesses corrected here.
Never roll back to the incomplete `rc.20` publication. If emergency availability
recovery requires `rc.19`, disable affected OAuth, SMTP, analytics, and export
surfaces first and return every component to `rc.21` as soon as possible.
Migration `0129` may remain applied because it does not rewrite application
rows. Restore the pre-upgrade database backup only when unrelated writes,
corruption, or the incident requires point-in-time recovery.
