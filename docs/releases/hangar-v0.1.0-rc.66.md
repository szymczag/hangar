## Security and privacy

**A project cover or workspace logo can no longer be used to delete someone
else's file.** Both columns used to accept the id of any asset. Completing the
next cover or logo upload then deleted whatever the column pointed at, treating
it as the previous one. So the creator of any project could remove another
project's cover, an attachment, or a file in another workspace by naming it
there and uploading a cover of their own. A project now accepts only its own
cover, a workspace only its own logo, and a new project accepts neither. The
deletion of the previous asset is also scoped to the entity it belongs to, so a
value written before this release cannot be used either.

**Only an admin changes a project's cover.** The cover is part of the project's
settings, which only a project admin or a workspace admin may edit. The asset
routes also let any project member create, replace, delete or restore it, which
was a way around those settings. They now apply the same two roles. The web app
already offered the cover picker to admins only, so no screen changes.

**Changing an asset inside a project requires membership of the project.** A
workspace admin who is not a member of a project could delete, restore or rebind
its attachments and description images, although they could not read them.
Membership now comes first, through the app and the v1 API alike. Within the
project, the uploader, a project admin and a workspace admin can still change
them as before.

**The proxy's Caddy is built on a patched Go.** The image scan of rc.65 left
the `proxy` image as the only one with fixable HIGH advisories, all of them in
the Caddy binary. Caddy moves from 2.11.4 to 2.11.7, built with Go 1.27.3 from
its official builder image, which fixes four standard-library advisories.
`golang.org/x/net` (0.60.0), `go-jose/v4` (4.1.6) and `grpc` (1.83.2) move past
theirs as well, and `klauspost/compress` arrives at 1.20.1 with Caddy 2.11.7. The
build checks x/crypto, x/net, x/text, grpc and go-jose/v4 in the binary it
produces, and refuses one built with a Go older than 1.27.3. The Caddyfile and
every proxy setting are unchanged.

## Migrations and compatibility

Upgrade from `0.1.0-rc.65`. This release carries **no database migrations** and
changes no schema. Update the API, workers, frontends and proxy together as
usual.

Two API answers change for a client outside the web app:

- A `PATCH` to a project or workspace that names any asset other than its own
  cover or logo in `cover_image_asset` or `logo_asset` now gets 400. `null` is
  still accepted.
- A workspace admin who is not a member of a project gets a refusal, not 204,
  when deleting, restoring or completing the upload of that project's
  attachments, including through the v1 API's attachment routes. To manage them,
  join the project first.

Product version is `v0.1.0-rc.66`, Git tag `hangar-v0.1.0-rc.66`, Helm chart
version `0.1.0-rc.66`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.66`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.65` are unchanged, apart from the
`proxy` image, whose advisories this release addresses. The `space` image still
carries its development dependencies.

Rolling back to rc.65 needs no schema change. It restores the looser asset rules
described above and the previous Caddy build.
