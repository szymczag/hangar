## Security and privacy

Repository history has been rewritten to remove private organisation-identifying
fixture data from published source and to remove the repository check that had
embedded the same data in an encoded form. Releases `rc.31` through `rc.38` are
retired; their GitHub Release records and attached assets are not supported.

The runtime source is otherwise equivalent to `rc.38`. It includes forced-private
publishing controls, operator-controlled external links and failure-page text,
retirement of invitations whose membership already exists, federated-account
email protection, and removal of Microsoft Clarity.

Compact work-item routes continue through the authenticated workspace layouts and
authorization boundary. A stale or unavailable default workspace uses the same
neutral not-found response and does not disclose workspace contents.

## Migrations and compatibility

Upgrade from the immediately previous retained GitHub release, `rc.30`, applies
twelve additive migrations:

- `ext.0013_openpgp_policy` and `ext.0014_federated_link_authorization`;
- `db.0130_spend_invitations_already_honoured`;
- `license.0013_api_token_minimum_role` through
  `license.0021_default_workspace_short_urls`.

They add policy records and seed instance configuration; no destructive data
backfill is required. Existing values, Secrets, storage, RBAC, and NetworkPolicy
contracts remain compatible.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.39`, the chart version is `0.1.0-rc.39`, the
signed Git tag is `hangar-v0.1.0-rc.39`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.39`. `rc.30` is the immediately previous
retained GitHub release. Releases `rc.31` through `rc.38` are retired and are not
upgrade or rollback targets.

## Known limitations and rollback

Hangar `rc.39` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

A technical rollback to `rc.30` can leave the additive tables and configuration
rows in place, but restores every defect fixed since that release and removes the
corresponding controls and user-visible features. Prefer a forward correction.
