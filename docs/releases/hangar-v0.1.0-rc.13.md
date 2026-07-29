## Security and privacy

`rc.13` fixes the two frontend runtime failures introduced by the React 19 and
Headless UI 2 update in `rc.12`. The SPA hydration fallback now returns the same
initial tree during prerendering and browser hydration. This removes React error
`#418` and prevents the hydration bailout that duplicated head resources. The
project-sidebar transition now renders an explicit DOM element, allowing Headless
UI to forward its transition ref when the transition has multiple children.

The release adds repository-wide runtime contract tests for deterministic
hydration fallbacks and structurally ref-safe Fragment-backed transitions. Those
tests run in the root check and the web pull-request workflow. The release change
adds no dependency, privilege, network request, authentication behavior,
user-input processing, unsafe rendering sink, telemetry destination, Secret
exposure, public object-storage route, chart permission, or network-policy
exception. The source change passed the web checks, React Doctor, and JavaScript
and Python CodeQL analysis before merge.

## Migrations and compatibility

There is no new Django database migration and no Helm values or Kubernetes
resource contract change in `rc.13`. The inherited Plane source remains
`v1.4.0-rc2`, whose root `package.json` reports version `1.4.0`. Existing
`rc.12` values remain compatible, but operators must render and review them
against the `0.1.0-rc.13` chart and deploy all application images as one Helm
revision.

Kubernetes 1.30 through 1.36, including 1.36.2, Helm 4.2, `linux/amd64`,
Restricted Pod Security Admission, TLS ingress with WebSocket support, a
`NetworkPolicy`-enforcing CNI, and persistent storage remain the qualified
boundary. The product version is `v0.1.0-rc.13`, the chart version is
`0.1.0-rc.13`, the signed Git tag is `hangar-v0.1.0-rc.13`, and the OCI chart
reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.13`.

## Known limitations and rollback

The inherited Plane version is a release candidate, and Hangar `rc.13` remains a
prerelease qualified for evaluation rather than production. Published images are
AMD64-only. `rc.12` is the immediately previous complete publication, but its web
application can fail during hydration or project-sidebar rendering after the
React 19 and Headless UI 2 upgrade. `rc.13` supersedes it.

Because `rc.12` and `rc.13` introduce no schema or data migration, an
application-only rollback from `rc.13` to the qualified `rc.11` rollback target
does not require a database restore solely because either release was deployed.
Replace every application component with the `rc.11` chart and images as one
coordinated revision. Do not use `rc.12` as the rollback target. Restore the
pre-upgrade database backup when unrelated writes, data corruption, or the
incident being handled requires point-in-time recovery.
