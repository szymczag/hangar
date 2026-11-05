## Security and privacy

**A visitor without a session no longer learns what the instance is.**
`/api/instances/` used to answer everyone with the instance's name, id, domain
and running version, the default workspace, the PostHog key and the internal base
URLs. Without a verified console session it now answers only what the sign-in and
failure pages render. A signed-in user reads the rest from
`/api/users/me/instance-config/`, which the web app loads with the current user.
Forgot-password gives the same answer whether or not an address has an account.
Anything outside the web app that read the version from `/api/instances/` has to
sign in now.

**More than forty of upstream Plane's security fixes from after v1.4.3 are in.**
None of them is in an upstream release yet. They bind every URL id to the URL
project (issues, modules, cycles, attachments, comments, history and deploy
boards). They also apply the restricted-guest rule to pages, search, the v1 API
and sub-resources, and make system and audit fields read-only. Exports are
limited to their owner, favorites to what the caller can see, and the v1 API's
archive route to a project role. Where Hangar already had a stricter rule, it was
kept. Behaviour an API client can notice:

- The v1 API answers 404 instead of 403 for a work item a restricted guest may
  not see.
- A handful of routed actions that had no authorization of their own answer 405.
  These are favorite lists, notification retrieve and delete, sticky retrieve and
  the remaining PUTs; the web app calls none of them.
- Publishing a project requires membership of it (upstream SECUR-247, from
  v1.4.3).

**Sessions and sign-in are harder to abuse.** Session, console and CSRF cookies
are `Secure` when the instance is served over https. A cookie-authenticated write
must come from the instance's own origin. The sign-in throttle also counts
signed-in callers, and it now covers changing a password and an email address.
An email-change code dies after five wrong attempts.

**Assets are served inline only as validated images.** A presigned URL renders
inline only for an allow-listed raster type, and that type is pinned on the
response. Anything else downloads as `application/octet-stream`, whatever type was
stored, because object storage can share the application's origin.

**Images in a new public-board comment upload again.** The public Space uploads a
comment image before the comment exists, and Hangar refused that upload. It is now
accepted unbound and attached when the comment is saved. Through Space, only an
asset's own uploader can delete, restore or rebind it.

**Dependencies are past every open advisory that has a fix.** PyJWT 2.15.0 closes
a critical key-confusion bypass. Django 5.2.17, Django REST framework 3.18.2 and
OpenTelemetry 1.45.2 are in as well. The Node packages are raised in one pass:
axios, dompurify, undici, vite, storybook, prosemirror-view, markdown-it,
follow-redirects, body-parser and zod 4, among others. CI now checks this on
every dependency change and nightly against the published images (pip-audit,
pnpm audit and Trivy). Trivy runs from its official image, pinned by digest and
signature-checked. GHSA-gvp8-978c-rx2q (PyJWT) has no fixed release; neither of
Hangar's callers can reach it.

## Migrations and compatibility

Upgrade from `0.1.0-rc.64`. This release carries **one database migration** in
the `db` application, and the ordinary release Job applies it.

**Docker Compose installs move from MinIO to SeaweedFS, and the move needs one
step.** MinIO stopped publishing community images, and the pinned MinIO image now
refuses anonymous pulls, so a fresh install could not start object storage at
all. `./setup.sh upgrade` runs the migration itself: it copies every bucket from
the old `uploads` volume into the new `object-storage` volume and verifies each one
by content. It never touches the old volume. `./setup.sh start` refuses to start
while the migration is pending rather than serve an empty store. On an install
whose object storage is external, set `SKIP_OBJECT_STORAGE_MIGRATION=1`. A Swarm
node that still holds the old volume stops the upgrade with instructions, because
volumes are node-local. The service name and the S3 port are unchanged, so
`AWS_S3_ENDPOINT_URL` and `plane.env` need no edit.

**A `rediss://` connection now verifies its certificate.** Valkey or Redis behind
a self-signed or private-CA certificate stops connecting until `REDIS_SSL_CA_CERTS`
names the CA, or the URL carries `ssl_cert_reqs=none`, which turns verification
off again as earlier releases did. The chart cannot mount a CA bundle, so on
Kubernetes the second is the temporary workaround, set in the cache Secret's URL.

**A deploy board that points at another project is repaired.** Migration `0134`
re-points every project board at its own project. When that project already has a
live board, the extra board is soft-deleted, which unpublishes it. Public Space endpoints answer
404 for a board that still disagrees with its project.

**Writes from another origin are refused.** A browser on a foreign origin gets 403
on cookie-authenticated API writes. A deployment that serves the frontends and the
API from the origins in its base URLs is unaffected. Behind more than one proxy,
set `NUM_PROXIES` (and `TRUSTED_PROXIES`) so the throttle sees the client's address
rather than the last proxy's. The Compose deployment passes both through, and its
`TRUSTED_PROXIES` default of `0.0.0.0/0` trusts every forwarded address, so narrow
it to the proxy's network where clients can reach the API directly.

**The evaluation chart's bundled SeaweedFS is hardened inside the Pod.** It moves
from 4.39 to 4.48 and signs filer and volume traffic with keys generated at each
start, so only the authenticated S3 port reaches objects even where NetworkPolicy
is not enforced. Telemetry, the admin UI and WebDAV are off. The values, Secret,
buckets and PVC are unchanged; `helm upgrade` rolls the StatefulSet once.
Production installs use external object storage and are unaffected.

Upstream Plane **v1.4.3** is backported, among its fixes voting on published
work items and archiving a cycle without an end date. It arrives as one signed
commit rather than a merge, because most of the upstream commits are unsigned, so
the recorded upstream revision stays at v1.4.0 (`917b23a6`): that is the newest
upstream commit in this release's history.

Product version is `v0.1.0-rc.65`, Git tag `hangar-v0.1.0-rc.65`, Helm chart
version `0.1.0-rc.65`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.65`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.64` are unchanged.

Rolling back to rc.64 is safe for the database: reversing migration `0134` is
allowed and does nothing, so the boards it repaired stay repaired, which the older build reads
without trouble. It is not safe for a Docker Compose install's uploads. rc.64
names a MinIO image that can no longer be pulled, and the old `uploads` volume
holds only what was there before the migration, so anything uploaded afterwards
exists only in `object-storage`. Take a backup with `./setup.sh backup` before
upgrading; `upgrade` does not take one itself.

The nightly image scan reports what is in the published images. Until this
release is published, it reports rc.64's dependencies. After it, it will still
report Alpine and Go packages that have no fixed release in the base images yet.
The `space` image also still carries its development dependencies. Both are being
worked through.

Trusted Types still ship observing rather than enforcing. The rich-text editor's
paste, broken on `preview` by two copies of `prosemirror-model` after the
`prosemirror-view` upgrade, was fixed before this release, and the Trusted Types
suite covers it again.
