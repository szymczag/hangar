## Security and privacy

**The space and live images no longer ship the build toolchain.** Both
images copied their `node_modules` from the build stage, which installs
development dependencies, so Vite, React Router's dev tooling, tsdown, vitest
and their dependencies shipped although nothing in the image runs them. Each image now installs its runtime dependencies separately, from the
same lockfile, without development dependencies and without install scripts.
`node_modules` shrinks from about 1 GB to 600 MB in `space` and from 1.2 GB to
715 MB in `live`, about 450 and 430 packages fewer. The all-in-one image takes
both, since it copies them from these images. Commands, ports and settings are
unchanged.

**A workspace created from the instance-admin console cannot start with
someone else's logo.** The console's workspace create still accepted any asset
id in `logo_asset`. The workspace screens refuse that since rc.66, because the
first logo upload deletes whatever the field points at, and the scoped deletion
in rc.66 already kept the file itself safe. The console now refuses the field on
create in the same way. Two unused helpers in the v1 API that deleted any asset
by id are removed.

**minimatch moves past its last open advisory.** GHSA-g3hv-75wg-m249 covers
minimatch 7 to 10 and is fixed only in 11.0.1. The 10 line, used only by eslint
in the development tools, now resolves to 11.0.4. Nothing that ships in an image
used it.

## Migrations and compatibility

Upgrade from `0.1.0-rc.66`. This release carries **no database migrations** and
changes no schema. Update the API, workers, frontends and the `live` service
together as usual. Nothing in the chart changes.

One API answer changes, for the instance-admin console only: a
`POST /api/instances/workspaces/` that names any asset in `logo_asset` now gets 400. Leaving it out, or sending `null`, still creates the workspace.

Product version is `v0.1.0-rc.67`, Git tag `hangar-v0.1.0-rc.67`, Helm chart
version `0.1.0-rc.67`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.67`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.65` are unchanged, apart from the
development dependencies, which `space` and `live` no longer carry. TypeScript
stays in both images: pnpm installs it automatically as an optional peer of
`@react-router/node` and `i18next`, and nothing runs it. The editor's Tiptap 2
carries a moderate `mergeAttributes` advisory that is fixed only in Tiptap 3.

Rolling back to rc.66 needs no schema change. It restores the larger images and
lets the console's workspace create accept a `logo_asset` again.
