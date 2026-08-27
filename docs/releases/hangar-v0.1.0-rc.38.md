## Security and privacy

Compact routes continue through the existing workspace authorization boundary, and an
unavailable selection uses the same neutral not-found response rather than
revealing workspace contents.

When the instance-wide external-links setting is off, the help icon is now
removed from the top navigation as well. It had remained an unconditional link
after the rest of the external destinations became operator-controlled.

**Workspace navigation.**

**The top navigation gives the workspace identity room to be legible.** Its
height is now 48 pixels, the workspace avatar is 36 pixels, and the workspace
name can use up to 288 pixels on wide screens. The search control yields space
responsively instead of forcing a long company name back into the old narrow
slot.

**One workspace can use compact work-item URLs.** God Mode can designate a
default workspace, after which its canonical work-item browse addresses are
shown as `/i/AA-123`. The choice is stored as a workspace UUID, so renaming the
workspace does not break its compact links. Other workspace routes and every
route in a non-default workspace keep their slug.

The compact route reuses the existing authenticated workspace layouts,
permissions, and work-item loader. A stale selection or a workspace the signed-in
account cannot access follows the existing neutral not-found path and does not
disclose its contents. Clearing the God Mode selection restores qualified browse
links.

**Live collaboration.**

**Published web images now keep collaboration below `/live`.** The frontend
previously accepted the Live origin from runtime configuration but read the Live
path only from a build-time variable, with an empty client fallback. A build that
lost that argument therefore attempted `/collaboration`, while the Live service
and proxy expose `/live/collaboration`.

The path is now present in runtime `config.js`, explicitly passed to release
image builds, and defaults to `/live` in the client. The chart render policy
checks the same value. This release must be deployed as a new web image; changing
only the Live container cannot repair a path compiled into an older frontend.

## Migrations and compatibility

One migration, `license.0021`, seeds `INSTANCE_DEFAULT_WORKSPACE_ID` as an empty,
unencrypted workspace setting. Empty means compact URLs are disabled. The API
accepts only an empty value or the UUID of an existing workspace and reports a
stale value as disabled.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.38`, the chart version is `0.1.0-rc.38`, the
signed Git tag is `hangar-v0.1.0-rc.38`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.38`. `rc.37` is the immediately previous
complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, `rc.28`, and
`rc.33` were consumed by incomplete publication attempts and are not upgrade or
rollback targets.

## Known limitations and rollback

Hangar `rc.38` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Rolling back to `rc.37` removes compact routes and the God Mode selection UI,
returns the smaller workspace identity area, and restores the frontend Live path
defect. The seeded configuration row remains in the database but `rc.37` ignores
it; no schema change needs reversing. Existing workspace-qualified links continue
to work in both releases.
