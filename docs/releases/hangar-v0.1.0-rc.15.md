## Security and privacy

`rc.15` completes the behavioral portion of the Headless UI 2 migration. Version
2 makes `Combobox.Options`, `Listbox.Options`, and `Menu.Items` modal by default.
Hangar retained Plane's externally controlled, Popper- and portal-based dropdown
pattern, so opening a dropdown could make focused task content inert and apply
`aria-hidden` to its ancestor. Headless UI could also close its internal state
without closing the externally rendered panel, leaving visible options that
could not be selected.

All 30 legacy option panels across the web, Space, admin, and shared UI packages
now explicitly preserve the non-modal Headless UI 1 contract. All 11 shared
`ComboDropDown` consumers synchronize internal close events with their external
state. Open and close callbacks use an immediate state ref to prevent duplicate
lifecycle callbacks during one interaction.

Import-aware contract tests scan only components imported from
`@headlessui/react`. They reject new modal legacy option panels and shared
combo-boxes that do not synchronize close state, without confusing Hangar's
separate Propel components with Headless UI components. A local headless
Chromium exercise used separate task and overlay DOM roots, selected a priority,
confirmed `aria-expanded=false`, and confirmed that the task root remained
`inert=false`.

The release adds no dependency, privilege, network request, authentication
behavior, user-input processing, unsafe rendering sink, telemetry destination,
Secret exposure, public object-storage route, chart permission, or
network-policy exception. The change passed runtime contracts, the full build,
type and lint checks, React Doctor, copyright validation, and JavaScript and
Python CodeQL before merge.

## Migrations and compatibility

There is no new Django database migration and no Helm values or Kubernetes
resource contract change in `rc.15`. The inherited Plane source remains
`v1.4.0-rc2`, whose root `package.json` reports version `1.4.0`. Existing
`rc.14` values remain compatible, but operators must render and review them
against the `0.1.0-rc.15` chart and deploy all application images as one Helm
revision.

Kubernetes 1.30 through 1.36, including 1.36.2, Helm 4.2, `linux/amd64`,
Restricted Pod Security Admission, TLS ingress with WebSocket support, a
`NetworkPolicy`-enforcing CNI, and persistent storage remain the qualified
boundary. The product version is `v0.1.0-rc.15`, the chart version is
`0.1.0-rc.15`, the signed Git tag is `hangar-v0.1.0-rc.15`, and the OCI chart
reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.15`.

## Known limitations and rollback

The inherited Plane version is a release candidate, and Hangar `rc.15` remains a
prerelease qualified for evaluation rather than production. Published images
are AMD64-only. `rc.14` is the immediately previous complete publication, but
its Headless UI 2 dropdown panels can make surrounding task content inert and
can become visually open while internally closed. `rc.13` and `rc.12` contain
the earlier frontend migration failures. `rc.15` supersedes those releases.

Because `rc.12` through `rc.15` introduce no schema or data migration, an
application-only rollback from `rc.15` to the qualified `rc.11` rollback target
does not require a database restore solely because one of those releases was
deployed. Replace every application component with the `rc.11` chart and images
as one coordinated revision. Do not use `rc.12`, `rc.13`, or `rc.14` as the
rollback target. Restore the pre-upgrade database backup when unrelated writes,
data corruption, or the incident being handled requires point-in-time recovery.
