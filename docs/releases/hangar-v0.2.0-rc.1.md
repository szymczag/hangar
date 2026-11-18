## Security and privacy

**Guests can no longer send page events to everyone else on a page.** The live
server already refused page events, such as a lock or archive notice, from a
guest's read-only connection, but any connection could still ask Hocuspocus to
relay a message to every other client on the page. On `0.1.4` a guest could use
that to make other people's page view show a lock, archive or visibility change
that never happened; nothing was stored. The Hocuspocus 3 client also obeys a
forced-close message, so the same relay would have let a guest stop other
clients from reconnecting. The live server now closes any client connection,
guest or editor, that sends such a broadcast. Server notices still reach every
client.

**The editor moves to Tiptap 3, which clears GHSA-cp6q-959q-f8rh.** The
advisory covers `mergeAttributes()` in `@tiptap/core`, which let a JSON
`__proto__` key turn into inherited DOM attributes such as `onerror`. The
`2.27.3` release Hangar shipped already carried the upstream guard, and a test
checked it, but the advisory lists every 2.x release, so dependency audits kept
reporting it. Hangar now uses `@tiptap/core` 3.31.3, and `pnpm audit --prod`
reports no known vulnerabilities. The editor's link, attribute, paste and markup
guards are kept, and run for both the browser and the server converter.

**The live server converts page HTML without running scripts or loading
resources.** Tiptap 3 converts HTML on the server through happy-dom instead of
the previous transformer. Each conversion runs in a window with JavaScript
evaluation, script and stylesheet loading and frame loading turned off, and
closes it afterwards. happy-dom is pinned to 21.0.4, past CVE-2026-115895, and a
test feeds script, event handler, `javascript:` and `data:` link, `srcdoc` and SVG
payloads through the converter.

**Completing an upload through the external API now needs access to its
project.** Besides being the upload's creator, the caller must be an active
member of the project the asset belongs to. The project cover hooks now look the
project up only inside the asset's workspace.

**PostHog support is removed.** Hangar never sent product analytics by default:
events went out only when an operator configured both `POSTHOG_API_KEY` and
`POSTHOG_HOST`. The PostHog client, its event tracking, both settings and the
`posthog_api_key` and `posthog_host` fields of the instance payload are gone,
along with the `posthog`, `backoff` and `monotonic` packages. Those two
variables are now ignored, and the API still refuses a stored PostHog
destination.

The API image no longer contains `pip`, `uv` or `psycopg-binary`; it installs
only the hash-locked production dependencies, still runs as uid 10001, and its
gRPC client reads the system CA bundle. In development settings, the Django
debug toolbar now loads only when `DEBUG` is on.

## Migrations and compatibility

**Pages move to Tiptap 3 and Hocuspocus 3.** The editor uses Tiptap 3.31.3 with
`@tiptap/y-tiptap` 3.0.9 in place of `y-prosemirror`, and the live server uses
Hocuspocus 3.4.4. Stored page documents and the editor schema do not change, so
no data is converted: the new live server reads pages written by `0.1.4` as
they are, and adds a title to a page that has none, as before. Browser tabs
opened before the upgrade reconnect and keep syncing, because the Hocuspocus 2
client and the Hocuspocus 3 server use the same message format. Reload them
anyway: they still run the `0.1.4` editor, and the new web image may no longer
serve the parts of the old app they load on demand. Upgrade `web` and `live`
together, as the installers and the Helm chart do.

**The API is built from a hash-locked dependency set.** Python dependencies are
declared in `apps/api/pyproject.toml` and pinned with hashes in
`apps/api/uv.lock`; the `requirements/` files are gone. The image keeps its
paths, entrypoints, base image and user. An image built on top of
`hangar-api` can no longer run `pip install`, because pip is not in it.

**The backend follows upstream Plane 1.5.0.** Apart from the changes above:

- The relation list of a work item now includes archived work items of the same
  project; archived work items of other projects stay hidden.
- Deleting a work item from a module a second time answers `204` instead of an
  error.
- A missing object-storage file is no longer logged as an error.
- Hangar keeps its stricter forms where upstream differs: sign-in throttles,
  OAuth state, asset permissions, comment rules, analytics scope and email
  comment rendering are unchanged.

This release adds no database or license migration, and the migrations lockfile
is unchanged. The Helm chart, its values and its Secrets, and the Compose,
Swarm and all-in-one deployment files do not change. The web app's source tree
and the editor package are reorganised the way upstream did; there is no
behaviour change for users.

Upgrade from `0.1.4`. This is a release candidate, so the installers do not
pick it on their own: run `HANGAR_RELEASE=v0.2.0-rc.1 ./setup.sh upgrade` (or
`swarm.sh`) with the `0.2.0-rc.1` script, use the `v0.2.0-rc.1` all-in-one
image, or run `helm upgrade` with `--version 0.2.0-rc.1` on Kubernetes. No other
operator action is required.

Product version is `v0.2.0-rc.1`, Git tag `hangar-v0.2.0-rc.1`, Helm chart
version `0.2.0-rc.1`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.2.0-rc.1`.

## Known limitations and rollback

This is a release candidate for `0.2.0`. `0.1.4` stays the current stable
release, and the installers keep choosing it unless you name this release.
Collaborative editing has passed automated tests, including a local run with
two live servers sharing Redis, but not yet a two-browser session of an editor
and a guest on a deployed stack.

The interface is still the Plane 1.4 design: the upstream 1.5.0 Propel redesign
is not included, and neither is Caddy for the web and admin images. The
recorded upstream base stays Plane 1.4.0 with the 1.4.3 changes backported. The
Kubernetes production profile has still not completed qualification, and the
all-in-one image does not send `Strict-Transport-Security` itself.

During a rolling upgrade or rollback on Kubernetes, the old and new `live` pods
share Redis for a short time. Their Redis channels and message format are the
same, but upstream did not test mixed Hocuspocus 2 and 3 servers; a page edited
during that window may need a reload.

**Rolling back to `0.1.4`** needs no schema change: only the images change.
Pages edited on this release stay readable by `0.1.4`. Tiptap 3 and Hocuspocus
3 store the same Yjs document: `@tiptap/y-tiptap` 3.0.9 encodes nodes, marks
and attributes with the same code as `y-prosemirror` 1.3.7, both use `yjs`
13.6.27, and upstream opened pages saved by Tiptap 3 in a Tiptap 2 build before
release. Rolling back brings back the guest broadcast relay, the upload
completion check without project access and the PostHog settings, and the API
image again contains `pip`.
