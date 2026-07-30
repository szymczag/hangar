## Security and privacy

`rc.16` completes the positioning portion of the Headless UI 2 migration.
Plane's inherited Headless UI 1 dropdown structure attached React Popper refs,
styles, and attributes to an inner `<div>` below `Combobox.Options`,
`Listbox.Options`, `Menu.Items`, or `Popover.Panel`. With Headless UI 2 and
React 19, that descendant did not become the active positioned panel. Popper
could therefore retain its initial absolute position at `(0, 0)`, making date,
priority, and similar selectors appear in the upper-left corner.

All 28 affected panels now own their Popper integration directly on the Headless
UI root: 17 combo boxes, 2 list boxes, 1 menu, and 8 popovers across the web,
Space, and shared UI packages. The change preserves the existing placements,
overflow modifiers, portals, transitions, and explicit non-modal behavior.
Repository contract tests now reject nested Popper targets and unsafe
Fragment-backed panels.

A minimal headless Chromium exercise placed a trigger at `(400, 300)`. The
inherited descendant-ref structure left its panel at `(0, 0)` and never
registered a Popper element; the corrected root-ref structure placed the panel
at `(400, 340)` and registered the expected element. The release also passed
runtime contracts, the full production build, type, format, and lint checks,
React Doctor, copyright validation, and JavaScript and Python CodeQL before
merge.

The release adds no dependency, privilege, network request, authentication
behavior, user-input processing, unsafe rendering sink, telemetry destination,
Secret exposure, public object-storage route, chart permission, or
network-policy exception.

## Migrations and compatibility

There is no new Django database migration and no Helm values or Kubernetes
resource contract change in `rc.16`. The inherited Plane source remains
`v1.4.0-rc2`, whose root `package.json` reports version `1.4.0`. Existing
`rc.15` values remain compatible, but operators must render and review them
against the `0.1.0-rc.16` chart and deploy all application images as one Helm
revision.

Kubernetes 1.30 through 1.36, including 1.36.2, Helm 4.2, `linux/amd64`,
Restricted Pod Security Admission, TLS ingress with WebSocket support, a
`NetworkPolicy`-enforcing CNI, and persistent storage remain the qualified
boundary. The product version is `v0.1.0-rc.16`, the chart version is
`0.1.0-rc.16`, the signed Git tag is `hangar-v0.1.0-rc.16`, and the OCI chart
reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.16`.

## Known limitations and rollback

The inherited Plane version is a release candidate, and Hangar `rc.16` remains a
prerelease qualified for evaluation rather than production. Published images
are AMD64-only. `rc.15` is the immediately previous complete publication, but
its Popper-positioned Headless UI panels can appear in the upper-left corner.
`rc.14`, `rc.13`, and `rc.12` contain the earlier frontend migration failures.
`rc.16` supersedes those releases.

Because `rc.12` through `rc.16` introduce no schema or data migration, an
application-only rollback from `rc.16` to the qualified `rc.11` rollback target
does not require a database restore solely because one of those releases was
deployed. Replace every application component with the `rc.11` chart and images
as one coordinated revision. Do not use `rc.12`, `rc.13`, `rc.14`, or `rc.15`
as the rollback target. Restore the pre-upgrade database backup when unrelated
writes, data corruption, or the incident being handled requires point-in-time
recovery.
