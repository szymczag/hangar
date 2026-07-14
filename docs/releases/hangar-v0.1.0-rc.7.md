## Security and privacy

`rc.7` incorporates the upstream fixes for GHSA-ch8j-vr4r-qf6h and
GHSA-wwgj-929g-42cm. Script-capable assets such as SVG, HTML, XML, and
JavaScript are now downloaded as attachments instead of being rendered inline,
and issue `group_by` and `sub_group_by` parameters are restricted to an
explicit allowlist before reaching Django ORM expressions.

The paid-plan upgrade dialog is replaced with Hangar Community information and
links to this repository's releases, source, and documentation. It does not add
telemetry or a commercial purchase flow. Evaluation object-storage access is
limited to the configured bucket route and the selected ingress or Gateway
data-plane Pods.

## Migrations and compatibility

There is no database migration. Current-user updates now preserve the previous
MobX state on failure and apply the server response on success, and uploaded
cover images are stored with both absolute and API-relative URLs.

The chart separates the object-storage address used by API and worker Pods
(`externalServices.objectStorage.endpoint`) from the browser-facing presigned
URL origin (`publicEndpoint`). Production requires HTTPS for both. Evaluation
installs leave `publicEndpoint` empty and route `/<bucket>` on the canonical
Hangar origin to the bundled SeaweedFS S3 port. Bucket names must be valid S3
names and must not collide with reserved application paths.

Ingress-controller NetworkPolicy configuration now uses the atomic
`networkPolicy.ingressController.preset` value: `nginx`, `envoyGateway`,
`traefik`, or `custom`. Existing values that override controller selectors must
select `custom` and provide complete namespace and Pod selectors. Gateway API
installs must select `envoyGateway`, `traefik`, or `custom`; the default `nginx`
preset is intentionally rejected in Gateway mode. Take coordinated PostgreSQL
and object-storage backups and use `--wait-for-jobs` during the upgrade.

## Known limitations and rollback

Evaluation browser uploads depend on the rendered `/<bucket>` Ingress or
HTTPRoute reaching SeaweedFS on port 8333. Production browsers must be able to
reach `publicEndpoint`, and the object-storage provider's TLS and CORS policy
must permit the configured Hangar origin. Named NetworkPolicy presets assume
the documented controller namespaces and labels; use `custom` when a cluster
uses different labels.

Rolling back application images and the chart to `rc.6` requires restoring the
previous object-storage and ingress-controller values. It does not require a
reverse database migration, but Helm rollback does not undo external storage,
CORS, Ingress, or Gateway changes. Rollback also reintroduces the two upstream
security issues fixed in this release, so prefer correcting deployment values
and completing the forward upgrade.
