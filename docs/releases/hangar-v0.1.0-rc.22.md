## Security and privacy

`rc.22` closes server-side request-forgery paths found during a repository-wide
review of outbound network calls. Live PDF export no longer passes a remote URL
or path to the renderer. It validates every DNS answer, rejects private and
reserved destinations unless an operator has allowed the exact hostname, pins
the connection to a validated address, and repeats those checks for each bounded
redirect. Responses have count, time, type, dimension, and byte limits and are
decoded and re-encoded as JPEG data URIs before rendering. Asset identifiers are
accepted only as canonical UUIDs.

The worker-to-Live `/convert-document/` route now requires the shared Live secret
and compares it in constant time. The chart exposes that secret only to Live and
the general worker. Operators whose presigned asset URLs intentionally resolve
to a private storage service can set exact hostnames in
`live.pdfAssetAllowedHosts`; the default remains empty.

The Unsplash proxy now sends only structured, bounded search parameters, places
the access key in a header, resolves and pins the configured service destination,
ignores ambient proxies, refuses redirects, and applies a request timeout. This
prevents user-controlled query text from changing the upstream origin or request
structure.

The PostHog destination is now deployment-owned. The instance configuration API
neither accepts nor returns a mutable PostHog host, and the runtime reads only the
environment setting. This removes a database-controlled outbound telemetry
destination. `cryptography` is updated to major version 50. Focused tests cover
the accepted and rejected destination, redirect, authentication, image-processing,
Unsplash, and PostHog paths. The editor also avoids unnecessary emoji canvas
reads; that change has no security or privacy impact.

## Migrations and compatibility

The release adds Django migration
`license.0009_remove_mutable_posthog_host`. It deletes any legacy
`POSTHOG_HOST` instance-configuration row. A deployment that intentionally uses
its own PostHog collector must set `POSTHOG_HOST` in the API and worker deployment
environment before upgrading; the removed database value cannot act as a
fallback. The supported Hangar chart does not expose a PostHog-host value, so the
default chart deployment requires no action.

The chart adds `live.pdfAssetAllowedHosts`, an empty-by-default list of exact
hostnames for intentionally private PDF asset origins. Existing `rc.21` values
remain structurally compatible. Public asset origins require no new setting.
The Live Secret contract is unchanged, but the general worker now consumes the
same `LIVE_SERVER_SECRET_KEY` as Live. Rotate that secret only with a coordinated
restart of both workloads.

Run the revision-scoped migration Job before admitting application traffic and
deploy API, workers, and Live as one Helm revision. The inherited Plane source
remains final `v1.4.0` at commit `917b23a6`; the Kubernetes qualification boundary
remains versions 1.30 through 1.36 (including 1.36.2), Helm 4.2,
`linux/amd64`, Restricted Pod Security Admission, TLS ingress with WebSocket
support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.22`, the chart version is
`0.1.0-rc.22`, the signed Git tag is `hangar-v0.1.0-rc.22`, and the OCI
chart reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.22`.
`rc.21` is the immediately previous complete publication. `rc.20` was consumed
by an incomplete publication attempt and is not an upgrade or rollback target.

## Known limitations and rollback

Hangar `rc.22` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

`live.pdfAssetAllowedHosts` is an explicit exception to the private-address
block, not a broad domain or CIDR allowlist. Use it only for exact operator-owned
storage hostnames and retain narrow network egress controls. Destination pinning
still applies. Re-encoding accepted raster images reduces parser and active-content
exposure, but it is not malware detection or a general content-disarm service.
The chart still has no supported value for a custom PostHog destination.

There is no security-equivalent rollback target. Rolling back to `rc.21`
restores the Live, Unsplash, and mutable PostHog destination weaknesses corrected
here. Migration `license.0009` permanently deletes the legacy PostHog row; a
rollback does not recreate it. If an emergency availability rollback is
unavoidable, disable PDF export, Unsplash, and PostHog traffic first, keep any
intentional PostHog destination in deployment configuration, and return every
component to `rc.22` as soon as possible. Restore a pre-upgrade database backup
only when unrelated writes, corruption, or the incident requires point-in-time
recovery.
