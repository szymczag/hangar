## Security and privacy

**Project members can no longer read or change each other's personal settings.**
The project member detail endpoint returned the whole membership row, so any
project member could read another member's `preferences`, `view_props` and
`default_props`, and a project admin could overwrite them. The response now
leaves those fields out unless the row is the caller's own, and a change to
another member's personal fields is refused. This backports the fix for upstream
Plane advisory
[GHSA-gx67-r6wp-3357](https://github.com/makeplane/plane/security/advisories/GHSA-gx67-r6wp-3357).

**Restricted guests can no longer reach files of work items hidden from them.**
In a project where guests may only see their own work items, a guest could
still download the attachments, description images and comment images of other
work items by asset ID, and could copy such a file into one of their own work
items. Every read, download, check and copy of a file by ID now applies the same
rule as the work item pages. This backports and extends the fix for upstream
Plane advisory
[GHSA-wq96-4xjj-j4qg](https://github.com/makeplane/plane/security/advisories/GHSA-wq96-4xjj-j4qg).

Every other upstream Plane advisory published since Hangar's 1.4.0 base was
checked against this release and is already fixed in Hangar.

**A failed upgrade download no longer leaves Hangar stopped.** `setup.sh
upgrade` now downloads and verifies the new release before it stops the
services. When the files cannot be downloaded or do not match the signed
`SHA256SUMS`, the running installation keeps running and nothing is changed.

**The all-in-one image replaces every template Live key.** A container started
with `LIVE_SERVER_SECRET_KEY=secret-key` now gets a generated key, as it already
did for the other template values, instead of Live refusing to start.

## Migrations and compatibility

This release adds no database migration and changes nothing in the Helm chart,
its values or its Secrets. Upgrade from `0.1.1` with the `0.1.2` `setup.sh` or
`swarm.sh`, or with `helm upgrade` on Kubernetes; no other action is required.

- `swarm.sh` now honours `HANGAR_RELEASE=vX.Y.Z`, like `setup.sh`, to deploy or
  upgrade to a named release without asking the GitHub API.
- `restore-airgapped.sh` is no longer published. It was the upstream script for
  an air-gapped bundle that Hangar does not ship, and it did not restore the
  object storage of a Hangar backup. Use `restore.sh`.
- A project admin's request that writes another member's `preferences`,
  `view_props` or `default_props` now answers `403`. The Hangar web app never
  sends one.

Upgrade from `0.1.1`. An upgrade from `0.1.1` to this release, followed by a
restore of its backup into a new installation, is tested as part of the release.

Product version is `v0.1.2`, Git tag `hangar-v0.1.2`, Helm chart version
`0.1.2`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.2`.

## Known limitations and rollback

The Kubernetes production profile has still not completed qualification, so do
not run the chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that does. Hangar is
still based on upstream Plane 1.4.0; the upstream 1.4.1 to 1.5.0 features are
not included.

**Rolling back to `0.1.1`** needs no schema change. Rolling back reopens the two
advisories above.
