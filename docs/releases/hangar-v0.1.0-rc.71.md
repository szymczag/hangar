## Security and privacy

**Release images carry current Alpine packages again.** The image scan of rc.70
found `libxslt` 1.1.43-r3 in the `web`, `admin` and `api` images, with two
high-rated flaws (CVE-2026-87636, CVE-2026-9947), and `krb5-libs` 1.22.1-r0 in
the `api` image, with sixteen high-rated flaws that Alpine has since fixed. The
images already upgrade their Alpine packages while they build, but release
builds reused that step from the build cache, so rc.70 shipped the packages of
an earlier build. Every release build now runs the upgrade afresh. When these
notes were written that installs `libxslt` 1.1.43-r4 and `krb5-libs` 1.22.3-r0,
which fix all eighteen. The images keep the same base images and contents
otherwise.

**Compose and Swarm installs on external storage no longer run an open object
store.** With `USE_MINIO=0` the API keeps uploads in external storage, but the
bundle still started its own object storage and the proxy still served it on
the application's origin. The installer leaves that store's login alone in this
mode, so with empty `AWS_*` values it ran on the `access-key` / `secret-key`
template pair, and anybody could store objects in it and have them served from
your domain. It held no Hangar uploads. With `USE_MINIO=0` the `plane-minio`
service now stays idle: it starts no storage, opens no port and reports
healthy, and the proxy no longer routes the bucket path to it. Installs with
`USE_MINIO=1`, the default, are unchanged.

**The live server moves to the fixed Effect release.** `effect` 3.22.4 and
`@effect/platform` 0.97 fix a cookie attribute injection in the platform's
cookie helpers (GHSA-chp3-j5qr-2vfr, CVE-2026-115779, rated medium). The live
server uses Effect only for PDF export and never builds cookies with it, so the
flaw was not reachable in Hangar. An unused development dependency that carried
an affected Effect beta has been removed.

## Migrations and compatibility

Upgrade from `0.1.0-rc.70`. This release adds no database migration and changes
no configuration, Helm value or Secret; no operator action is required. The
Compose upgrade downloads the release's `docker-compose.yml`, which passes
`USE_MINIO` to the proxy and the object storage, so an install on external
storage no longer needs `plane-minio` removed by hand. The Helm chart does not
use the bundled proxy or object storage and is unchanged.

Product version is `v0.1.0-rc.71`, Git tag `hangar-v0.1.0-rc.71`, Helm chart
version `0.1.0-rc.71`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.71`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.70` are unchanged, except that the
object storage of an install on external storage no longer runs, as described
above. An install that points `AWS_S3_ENDPOINT_URL` at external storage but
leaves `USE_MINIO=1` still starts the bundled store; set `USE_MINIO=0` in that
case.

Rolling back to `0.1.0-rc.70` needs no schema change and brings back its
Alpine packages, the earlier Effect release and, on Compose and Swarm installs
with `USE_MINIO=0`, the running object store. Rolling back further, to
`0.1.0-rc.69`, needs no schema change either. Rolling back to `0.1.0-rc.68`
needs the rc.69 migration reversed first, as the rc.69 notes describe.
