## Security and privacy

`rc.14` completes the Headless UI 2 migration that remained incomplete in
`rc.13`. Shared combo-box triggers now let `Combobox.Button` render and own a
native `<button>`. Headless UI can therefore attach its ref, accessibility
attributes, state, keyboard handling, pointer handling, and focus behavior
directly instead of attempting to pass them through a React Fragment.

The migration covers member, module, project, intake-state, priority, state,
estimate, and cycle selectors. Repository-wide contract tests execute the
previously failing Fragment-backed button case and the supported native-button
case. They also scan all applications and packages for Fragment-backed Headless
UI components and verify that every shared combo-box trigger resolves to a native
button.

The release adds no dependency, privilege, network request, authentication
behavior, user-input processing, unsafe rendering sink, telemetry destination,
Secret exposure, public object-storage route, chart permission, or
network-policy exception. The source change passed the full build, type, lint,
format, runtime contract, React Doctor, and JavaScript and Python CodeQL checks
before merge.

## Migrations and compatibility

There is no new Django database migration and no Helm values or Kubernetes
resource contract change in `rc.14`. The inherited Plane source remains
`v1.4.0-rc2`, whose root `package.json` reports version `1.4.0`. Existing
`rc.13` values remain compatible, but operators must render and review them
against the `0.1.0-rc.14` chart and deploy all application images as one Helm
revision.

Kubernetes 1.30 through 1.36, including 1.36.2, Helm 4.2, `linux/amd64`,
Restricted Pod Security Admission, TLS ingress with WebSocket support, a
`NetworkPolicy`-enforcing CNI, and persistent storage remain the qualified
boundary. The product version is `v0.1.0-rc.14`, the chart version is
`0.1.0-rc.14`, the signed Git tag is `hangar-v0.1.0-rc.14`, and the OCI chart
reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.14`.

## Known limitations and rollback

The inherited Plane version is a release candidate, and Hangar `rc.14` remains a
prerelease qualified for evaluation rather than production. Published images are
AMD64-only. `rc.13` is the immediately previous complete publication, but shared
dropdowns can fail when Headless UI forwards button props through a Fragment.
`rc.12` additionally has hydration and transition failures. `rc.14` supersedes
both releases.

Because `rc.12`, `rc.13`, and `rc.14` introduce no schema or data migration, an
application-only rollback from `rc.14` to the qualified `rc.11` rollback target
does not require a database restore solely because one of those releases was
deployed. Replace every application component with the `rc.11` chart and images
as one coordinated revision. Do not use `rc.12` or `rc.13` as the rollback
target. Restore the pre-upgrade database backup when unrelated writes, data
corruption, or the incident being handled requires point-in-time recovery.
