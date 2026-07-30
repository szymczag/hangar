## Security and privacy

`rc.17` completes the visibility and interaction portion of the Headless UI 2
Popper migration. `rc.16` correctly moved Popper refs, styles, and attributes
onto the Headless UI panel root, but most panels still rendered inside task
layout ancestors using `overflow-hidden` or `overflow-y-auto`. Those panels
could have correct coordinates while being clipped and appear not to open.
Manually portaled panels could also render below surrounding content because
their stacking layer remained on an unpositioned child.

All Popper-backed Headless UI panels now escape clipping ancestors through the
native Headless UI portal or an existing explicit portal. Each positioned panel
root owns an explicit stacking layer and protects portaled interactions from
surrounding outside-click handlers. Three Popper-backed popovers missed by the
earlier migration now follow the same root-ref contract. The shared
single-select commits a selected value before closing so pointer selection
cannot be discarded by close ordering.

A headless Chromium exercise imported the actual `@plane/ui` single-select
inside an `overflow-hidden` fixture. The panel was created under a Headless UI
portal, positioned beside its trigger, remained visible, and a complete pointer
sequence changed the value from `a` to `b` before closing it. Repository
contract tests now reject every Popper-backed Headless UI panel that lacks a
portal, outside-click protection, an explicit root stacking layer, or a root
Popper ref. The release also passed runtime contracts, the full production
build, type, format, and lint checks, React Doctor, copyright validation, and
JavaScript and Python CodeQL before merge.

The release adds no dependency, privilege, network request, authentication
behavior, user-input processing, unsafe rendering sink, telemetry destination,
Secret exposure, public object-storage route, chart permission, or
network-policy exception.

## Migrations and compatibility

There is no new Django database migration and no Helm values or Kubernetes
resource contract change in `rc.17`. The inherited Plane source remains
`v1.4.0-rc2`, whose root `package.json` reports version `1.4.0`. Existing
`rc.16` values remain compatible, but operators must render and review them
against the `0.1.0-rc.17` chart and deploy all application images as one Helm
revision.

Kubernetes 1.30 through 1.36, including 1.36.2, Helm 4.2, `linux/amd64`,
Restricted Pod Security Admission, TLS ingress with WebSocket support, a
`NetworkPolicy`-enforcing CNI, and persistent storage remain the qualified
boundary. The product version is `v0.1.0-rc.17`, the chart version is
`0.1.0-rc.17`, the signed Git tag is `hangar-v0.1.0-rc.17`, and the OCI chart
reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.17`.

## Known limitations and rollback

The inherited Plane version is a release candidate, and Hangar `rc.17` remains a
prerelease qualified for evaluation rather than production. Published images
are AMD64-only. `rc.16` is the immediately previous complete publication, but
its Popper-positioned Headless UI panels can be clipped by task layout overflow
or hidden behind surrounding content. `rc.15`, `rc.14`, `rc.13`, and `rc.12`
contain the earlier frontend migration failures. `rc.17` supersedes those
releases.

Because `rc.12` through `rc.17` introduce no schema or data migration, an
application-only rollback from `rc.17` to the qualified `rc.11` rollback target
does not require a database restore solely because one of those releases was
deployed. Replace every application component with the `rc.11` chart and images
as one coordinated revision. Do not use `rc.12`, `rc.13`, `rc.14`, `rc.15`, or
`rc.16` as the rollback target. Restore the pre-upgrade database backup when
unrelated writes, data corruption, or the incident being handled requires
point-in-time recovery.
