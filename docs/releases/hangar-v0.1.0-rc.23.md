## Security and privacy

`rc.23` updates Django from 5.2.15 to the upstream security release 5.2.16.
It incorporates fixes for three issues rated low severity under Django's security
policy: CVE-2026-48588, which could cache a response that sets a sensitive cookie
when the request already carried an unrelated cookie; CVE-2026-53877, a bounded
heap over-read when `GDALRaster` loads raster bytes through GDAL's virtual
filesystem; and CVE-2026-53878, which allowed newline characters through
`DomainNameValidator` and could enable header injection when a validated value
was later used outside Django's newline-protected response APIs.

Hangar does not enable Django's site-wide cache middleware. Its direct
`cache_page` use is limited to the public timezone-list endpoint, and the review
found no direct `GDALRaster` or `DomainNameValidator` call site. The framework
update still removes the vulnerable behavior from the supported runtime and
protects indirect and future uses. No telemetry, authentication, authorization,
secret-handling, or outbound-destination policy changes are included.

All application, API, dependency, security-migration, import, lint, type, and
CodeQL checks passed on the dependency pull request before it was merged.

## Migrations and compatibility

There is no new Django database migration, Helm value, Secret, Kubernetes
resource, public route, storage, RBAC, or NetworkPolicy change in this release.
Existing `rc.22` values and deployment configuration remain structurally
compatible, and no operator configuration action is required.

Deploy the API, migrator, and workers as one Helm revision so every Python
process uses Django 5.2.16. The normal revision-scoped migration Job must still
complete before application traffic is admitted even though it has no new schema
operation to apply.

The inherited Plane source remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.23`, the chart version is
`0.1.0-rc.23`, the signed Git tag is `hangar-v0.1.0-rc.23`, and the OCI
chart reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.23`.
`rc.22` is the immediately previous complete publication. `rc.20` was consumed
by an incomplete publication attempt and is not an upgrade or rollback target.

## Known limitations and rollback

Hangar `rc.23` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

The Django fixes reduce framework-level risk but do not replace application
cache isolation, response-header validation, safe raster processing, or defense
in depth at ingress and egress boundaries. Operators should continue to treat
shared caches and untrusted raster data according to their deployment threat
model.

There is no security-equivalent rollback target. Rolling back to `rc.22`
restores Django 5.2.15 and the three corrected framework behaviors. No database
or configuration conversion blocks a technical rollback, but an emergency
rollback should disable affected cache or raster-processing paths where present
and return every Python component to `rc.23` as soon as possible. Restore a
database backup only when unrelated writes, corruption, or the incident requires
point-in-time recovery.
