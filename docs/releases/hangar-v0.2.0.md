## Security and privacy

**Real-time collaboration works again; on 0.1.3 and 0.1.4 concurrent edits
were lost.** In stable `0.1.3` and `0.1.4` the live server could never load or
store a page: every collaboration connection logged `Missing required fields`.
Co-editing in real time did not work, and pages were saved only by the
browser's HTTP fallback, so when two people edited the same page at once the
last one to save won and the other's changes were lost. The cause was the
per-connection page access check added in `0.1.3` (commit `77333d3abc`). It set
the page's project on a context object that Hocuspocus 2.15 discards when it
does not await `onAuthenticate` before `onConnect`, so the page loader never saw
the project. This release moves the live server to Hocuspocus 3, which fixes
it. The deployment tests of the release candidates verified it with two editors
and a guest on one page: edits propagated live, and the merged text was stored.
Everybody on `0.1.3` or `0.1.4` who edits pages together should upgrade.

**God Mode stays locked when its only security key has been disabled.** The
server disables a security key whose signature counter goes backwards, as a
suspected clone. On `0.1.4` the next password sign-in then treated the
administrator as never enrolled and offered key enrollment, so a password alone
was enough to register a new key in place of the one just flagged. Now a
sign-in whose administrator has only disabled keys is refused with code `5198`,
and the console says the key was disabled and must be reset from a shell. Only
`python manage.py disable_instance_admin_2fa --email …` re-opens enrollment,
and its `--list` output now shows which keys are disabled. The registration
endpoints refuse the same state on their own, and a pending enrollment can only
register an administrator's first key. A God Mode session that is already
signed in when its last key is disabled stays valid until it expires or signs
out, but it can no longer add a key. Administrators who never enrolled a key
enroll as before. See [God Mode second factor](../god-mode-second-factor.md).

**The all-in-one image now sends the frontend security headers.** On `0.1.4`
the web app (`/`) and God Mode (`/god-mode/`) in the all-in-one image were
served with no security headers, so they could be framed by another site. They
now send the same headers as the Compose and Helm images: the
Content-Security-Policy generated from each build with its script hashes and
`frame-ancestors 'none'`, the Trusted Types policy in report-only mode,
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and
`Referrer-Policy: strict-origin-when-cross-origin`. The `HANGAR_CSP_*`
variables work as in Compose. The container refuses to start if it cannot
render the headers, so the frontends are never served without them. The image
still does not send `Strict-Transport-Security`; put it behind a proxy that
adds it if you need it.

**Guests can no longer send page events to everyone else on a page.** The live
server already refused page events, such as a lock or archive notice, from a
guest's read-only connection, but any connection could still ask Hocuspocus to
relay a message to every other client on the page. On `0.1.4` a guest could use
that to make other people's page view show a lock, archive or visibility change
that never happened; nothing was stored. The Hocuspocus 3 client also obeys a
forced-close message, so the same relay would have let a guest stop other
clients from reconnecting. The live server now closes the page connection of
any client, guest or editor, that sends such a broadcast. Server notices still
reach every client.

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

The server document converters are not part of the editor package's main
entry, so the `space` server bundle, which never converts documents, does not
contain happy-dom. In the candidates `0.2.0-rc.1` and `0.2.0-rc.2` it did, and
with it the public test key that happy-dom ships for its own HTTPS tests, which
image scanners reported as a private key. It was never a Hangar secret.

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

**The proxy's Caddy is built with Go 1.27.4.** The image scan of
`0.2.0-rc.3` found CVE-2026-97054 (HIGH) in the Go standard library compiled
into the proxy's `caddy` binary, which the all-in-one image also uses. The
official Caddy builder images still ship Go 1.27.3, so the proxy is now built
with the Go 1.27.4 toolchain; Caddy itself (v2.11.7), its plugins and its
configuration are unchanged.

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

**The all-in-one image starts `space` and accepts a port in `DOMAIN_NAME`.**
Since `0.1.0`, supervisord in the all-in-one image could not find the `space`
command, the program went `FATAL`, and `/spaces/` answered `502`. It now starts,
and published boards are served. `DOMAIN_NAME` now accepts `host:port`; the port
is kept in `WEB_URL` and `CORS_ALLOWED_ORIGINS`, so an instance published on a
non-standard port no longer redirects without it. Because uploads go straight
to object storage, the origin of `AWS_S3_PUBLIC_ENDPOINT_URL` (else
`AWS_S3_ENDPOINT_URL`) and the bucket's virtual-hosted subdomain of it are
added to the policy's `img-src`, `connect-src` and `media-src`, for web, God
Mode and space alike. An all-in-one deployment that embedded the web app in a
frame on another site stops working, as it already did on Compose and Helm.

**The Helm production profile allows the object-storage origin the API
signs.** With external S3 and `externalServices.objectStorage.pathStyle: false`,
the default, the frontends' Content-Security-Policy allowed only the bucket's
virtual-hosted origin, such as `https://hangar.s3.example.com`, while the API
signs path-style URLs on the endpoint, such as `https://s3.example.com/hangar/`.
Browser uploads and stored images were blocked. The chart now always allows the
endpoint origin (`publicEndpoint`, else `endpoint`), and with `pathStyle: false`
also the bucket's virtual-hosted origin; that second origin is left out for an
IP-address endpoint or a bucket name with a dot. The evaluation profile is
unchanged. No values change is needed: `helm upgrade` renders the new origins.

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

This release adds no database or license migration compared with `0.1.4`, and
the migrations lockfile is unchanged. The Helm chart's values and Secrets do not
change; its templates change only in the object-storage origins described
above. The Compose and Swarm deployment files do not change. The all-in-one
image changes only as described above. The web app's source tree and the editor
package are reorganised the way upstream did; there is no behaviour change for
users.

Upgrade from `0.1.4`. The installers now pick `0.2.0` on their own: run
`./setup.sh upgrade` (or `swarm.sh upgrade`) with the `0.2.0` script. Use the
`v0.2.0` all-in-one image, which the `stable` tag now also points to, or run
`helm upgrade` with `--version 0.2.0` on Kubernetes. No other operator action is
required. An installation on any `0.2.0` release candidate upgrades the same
way; `0.2.0` is built from the `0.2.0-rc.3` source plus its release notes,
its version and the Go 1.27.4 rebuild of the proxy described above. An upgrade from `0.1.4` to this release, followed by a
restore of its backup into a new installation, is tested as part of the
release.

Product version is `v0.2.0`, Git tag `hangar-v0.2.0`, Helm chart version
`0.2.0`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.2.0`.

## Known limitations and rollback

`0.2.0-rc.1`, `0.2.0-rc.2` and `0.2.0-rc.3` were release candidates for this
release and are superseded by it. `0.2.0-rc.1` was published to the registry,
images and Helm chart, but has no GitHub Release because of a workflow bug. The
previous stable release, for upgrades and rollback, is `0.1.4`.

Besides the automated tests, the candidates passed deployment tests.
`0.2.0-rc.2` was upgraded with Compose from `0.1.4` with no migrations run and
an identical data fingerprint; in a two-browser collaboration session with an
editor and a guest, the guest's connection was read-only and its forced edits
were refused; it was rolled back to `0.1.4` and upgraded again. `0.2.0-rc.3`,
the source of this release, passed its deployment test on 2026-11-19: a Compose
upgrade from `0.2.0-rc.2` that ran no migrations and left the data fingerprint
identical; the functional and collaboration suites; the God Mode lockout after a
disabled key and its reset from a shell; the all-in-one image with `space`
serving published boards, the frontend security headers, an upload under the
enforced Content-Security-Policy and a `DOMAIN_NAME` with a port; and rendering
the Helm chart. Kubernetes was not installed on a cluster in either test, so on
Kubernetes this release stays qualified for evaluation on AMD64 only, as before.

The interface is still the Plane 1.4 design: the upstream 1.5.0 Propel redesign
is not included, and whether to adopt it is a separate, later decision. Caddy
for the web and admin images is not included either. The recorded upstream base
stays Plane 1.4.0 with the 1.4.3 changes backported. The Kubernetes production
profile has still not completed qualification, and the all-in-one image does
not send `Strict-Transport-Security` itself.

Other known limitations:

- When God Mode refuses a sign-in with `5198`, the reset command it shows reads
  `--email <your email>` instead of the administrator's address. Substitute the
  address yourself; the message is otherwise correct.
- The all-in-one container does not shut down gracefully. Its start script
  does not `exec` supervisord, so the stop signal does not reach it, and
  `docker stop` waits its 10-second timeout and then kills the container.
- On the all-in-one image, `/spaces` without a trailing slash serves the web app
  instead of space. Use `/spaces/` with the trailing slash.

During a rolling upgrade or rollback on Kubernetes, the old and new `live` pods
share Redis for a short time. Their Redis channels and message format are the
same, but upstream did not test mixed Hocuspocus 2 and 3 servers; a page edited
during that window may need a reload.

**Rolling back to `0.1.4` brings the collaboration bug back.** Do not roll back
unless you need to. If you do, ask users not to edit the same page at the same
time, because concurrent edits are lost again. The rollback itself needs no
schema change and no change to the Helm values: only the images change. An
all-in-one installation that follows the `stable` tag has to name `v0.1.4`
to roll back, because `stable` now points to `0.2.0`. Pages edited on this
release still open on `0.1.4`; the `0.2.0-rc.2` deployment test verified this
by rolling back on the same volumes, with only the images changed. Tiptap 3 and Hocuspocus 3 store
the same Yjs document: `@tiptap/y-tiptap` 3.0.9 encodes nodes, marks and
attributes with the same code as `y-prosemirror` 1.3.7, both use `yjs`
13.6.27, and upstream opened pages saved by Tiptap 3 in a Tiptap 2 build before
release. Rolling back also brings back the God Mode enrollment after a disabled
key, the all-in-one image's missing `space` and frontend security headers, the
blocked uploads of the Helm production profile with `pathStyle: false`, the
guest broadcast relay, the upload completion check without project access and
the PostHog settings, and the API image again contains `pip`.
