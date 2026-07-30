## Security and privacy

`rc.18` repairs the stacking contract for the portaled Headless UI panels
introduced by `rc.17`. Those panels escaped clipping ancestors, but their local
`z-10` or `z-30` layers remained below issue peeks and dialogs using layers
through `z-100`. A panel could therefore be visible while browser hit testing
sent pointer events to the dialog above it, preventing changes to priority,
labels, modules, dates, and other fields.

Every Popper root marked with `data-popper-placement` now uses a centralized
floating-overlay layer of `110`. This places interactive panels above all
current dialogs and issue peeks while retaining the notification layer at
`1000`. The rule covers all 33 Popper targets and deliberately overrides stale
component-local stacking classes. A repository contract test verifies both the
shared layer and that every JSX Popper ref owns its Popper attributes.

A local Chromium exercise used real pointer input inside a dialog and confirmed
Priority changed from none to high, Modules from none to alpha, and Labels from
none to security. The production build, lint, type, format, and contract checks
passed before release.

The change adds no dependency, privilege, network request, authentication
behavior, user-input processing, unsafe rendering sink, telemetry destination,
Secret exposure, public object-storage route, chart permission, or
network-policy exception.

## Migrations and compatibility

There is no new Django database migration and no Helm values or Kubernetes
resource contract change in `rc.18`. The inherited Plane source remains
`v1.4.0-rc2`, whose root `package.json` reports version `1.4.0`. Existing
`rc.17` values remain compatible, but operators must render and review them
against the `0.1.0-rc.18` chart and deploy all application images as one Helm
revision.

Kubernetes 1.30 through 1.36, including 1.36.2, Helm 4.2, `linux/amd64`,
Restricted Pod Security Admission, TLS ingress with WebSocket support, a
`NetworkPolicy`-enforcing CNI, and persistent storage remain the qualified
boundary. The product version is `v0.1.0-rc.18`, the chart version is
`0.1.0-rc.18`, the signed Git tag is `hangar-v0.1.0-rc.18`, and the OCI chart
reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.18`.

## Known limitations and rollback

The inherited Plane version is a release candidate, and Hangar `rc.18` remains
a prerelease qualified for evaluation rather than production. Published images
are AMD64-only. `rc.17` is the immediately previous complete publication, but
its portaled Popper panels can render below dialogs and issue peeks, preventing
pointer selection. `rc.16`, `rc.15`, `rc.14`, `rc.13`, and `rc.12` contain
earlier frontend migration failures. `rc.18` supersedes those releases.

Because `rc.12` through `rc.18` introduce no schema or data migration, an
application-only rollback from `rc.18` to the qualified `rc.11` rollback target
does not require a database restore solely because one of those releases was
deployed. Replace every application component with the `rc.11` chart and images
as one coordinated revision. Do not use `rc.12`, `rc.13`, `rc.14`, `rc.15`,
`rc.16`, or `rc.17` as the rollback target. Restore the pre-upgrade database
backup when unrelated writes, data corruption, or the incident being handled
requires point-in-time recovery.
