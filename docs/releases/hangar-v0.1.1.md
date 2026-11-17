## Security and privacy

**Rebuilt images fix the reported Alpine vulnerabilities.** The nightly scan of the
`0.1.0` images reported fixable HIGH findings in the `api` image, all in the
Alpine `libpq` package (18.6-r0, fixed in 18.7-r0). Every image in this release
is rebuilt with the current Alpine packages. No application code change was
needed.

**Compose and Swarm installs no longer run with published secrets.**
`variables.env` used to ship `SECRET_KEY` and `LIVE_SERVER_SECRET_KEY` as
`change-this-key-on-deployment`, and the database and RabbitMQ passwords as
`plane`. Anybody who knows a published `SECRET_KEY` can forge sessions,
password-reset links and CSRF tokens.

- `setup.sh` and `swarm.sh` now generate both keys whenever they are empty or a
  template value, on install and on upgrade.
- A fresh install also gets generated database and RabbitMQ passwords.
- The API containers refuse to start with an empty or template `SECRET_KEY`.
  Live refuses an empty or template `LIVE_SERVER_SECRET_KEY`.
- `DATABASE_URL` and `AMQP_URL` are now built from the `POSTGRES_*` and
  `RABBITMQ_*` settings instead of a fixed `plane:plane` URL.

**Compose services run with fewer privileges.** Every service runs with `no-new-privileges`. The
application containers and the object store drop all Linux capabilities; the
proxy keeps only `NET_BIND_SERVICE`. PostgreSQL, Valkey and RabbitMQ are pinned
by digest and have healthchecks, as does the API.

**Release assets are signed, checksummed and described by SBOMs.** Each release now publishes:

- `release-manifest.json`, naming every image by digest;
- one SPDX SBOM per image (`hangar-<image>.spdx.json`);
- `SHA256SUMS` with a keyless Cosign bundle (`SHA256SUMS.sigstore.json`) signed
  by the release workflow for this tag.

The `docker-compose.yml` asset now pins every Hangar image by digest. `setup.sh`
and `swarm.sh` check the downloaded files against `SHA256SUMS` before using
them, and also check the signature when `cosign` is installed.
`HANGAR_REQUIRE_SIGNATURE=1` makes a missing signature an error. A failed
release download no longer falls back silently to files from the `preview`
branch.

**The release pipeline is pinned and linted.**

- Every GitHub Action is pinned to a commit and checked by actionlint and zizmor.
- Django's deployment checklist runs in CI against the production settings.
- The password-reset token contract (single use, expiry, bound to its user) is
  covered by tests.
- Accepted scanner findings must carry an expiry date.
- A weekly job tracks upstream Plane releases and security advisories.

## Migrations and compatibility

This release adds no database migration and changes nothing in the Helm chart,
its values or its Secrets. On Kubernetes and the all-in-one image no operator
action is required: the chart takes its secrets from the operator, and the
all-in-one image already generated its keys.

On Docker Compose and Swarm, upgrade with the `0.1.1` `setup.sh` or `swarm.sh`:

- **Everybody is signed out once** if `SECRET_KEY` was empty or a template
  value, because the installer replaces it. Password-reset links that are still
  pending stop working. Workspace and project invitation links keep working.
  Instance settings saved in God Mode under the template key, such as the SMTP
  password and OAuth client secrets, are re-encrypted with the new key when the
  API starts.
- **Database and RabbitMQ passwords are not rotated on an upgrade.** If they
  are still `plane`, the installer prints a warning. The Compose README
  describes how to change them.
- **Google Calendar capacity.** If `ENABLE_GOOGLE_CALENDAR_CAPACITY=1` is set
  and the key is still a template value, the installer stops before changing
  anything. Replacing the key changes the stored calendar and training
  identifiers. Read the Compose README first, then rerun with
  `HANGAR_ROTATE_SECRET_KEY=1`.
- **Unattended and local builds.** Unattended upgrades can use `--yes` or
  `HANGAR_ASSUME_YES=1`. Building the images locally now uses a generated
  `docker-compose.override.yaml`.
- **`restore.sh` restores object storage correctly.** It now gives the
  restored object-storage volume to the user the store runs as, so uploads work
  after a restore on Docker. It also reports a failure and exits with an error
  when any volume cannot be restored, instead of reporting success.
- **Do not start the `0.1.1` images with an old `plane.env` that still holds the
  template key** (for example by editing the image tag by hand): the API exits
  with code 64 and explains what to set.

Upgrade from `0.1.0`. An upgrade from `0.1.0` to this release, followed by a
restore of its backup into a new installation, is tested as part of the release.

Product version is `v0.1.1`, Git tag `hangar-v0.1.1`, Helm chart version
`0.1.1`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.1`.

## Known limitations and rollback

The Kubernetes production profile has still not completed qualification, so do
not run the chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that does.

**Behaviour that can surprise an operator:**

- If verification fails during `setup.sh upgrade`, the installer leaves every
  file unchanged, but the services stay stopped until the operator runs `start`.
- Releases up to `0.1.0` have no `SHA256SUMS`. Installing them prints a warning,
  or stops with `HANGAR_REQUIRE_SIGNATURE=1`.

**Rolling back to `0.1.0`** needs no schema change. Keep the `plane.env` that
the `0.1.1` installer wrote, because its generated keys must stay. Going back to
the template key would sign everybody out again and break the re-encrypted God
Mode settings. An installation first created with `0.1.1` has generated database
and RabbitMQ passwords, which the `0.1.0` Compose file ignores because it
connects with a fixed `plane:plane` URL. Before rolling such an installation
back, set `DATABASE_URL` and `AMQP_URL` in `plane.env` explicitly. Rolling back
the images does not roll back migrations, and this release has none, so a
restore is not needed.
