## Security and privacy

**Markdown rendering no longer lets a crafted text tie up an API worker.** The
API rendered Markdown with mistune 3.3.3, which takes quadratic time on two
kinds of input:

- links with an empty label, in `parse_link_href`
  ([GHSA-phmp-hrw4-r36r](https://github.com/advisories/GHSA-phmp-hrw4-r36r),
  CVE-2026-97698, HIGH);
- inline images
  ([GHSA-ww7q-mxrj-5ffg](https://github.com/advisories/GHSA-ww7q-mxrj-5ffg),
  CVE-2026-97699, HIGH).

Both advisories were published on 2026-11-19, after `0.2.0` was built. The API
renders Markdown that signed-in users submit, so on `0.2.0` such a user could
keep an API worker's CPU busy with one crafted text. Nothing is exposed: no
data can be read or changed this way. Hangar now ships mistune 3.3.4, which
fixes both; no other package changes. The rendered HTML is still sanitised by
nh3 afterwards, as before. The image scan of `0.2.0` reported both advisories
in the `api` image, which the all-in-one image also contains.

**The God Mode reset hint names the administrator's address.** When God Mode
refuses a sign-in with `5198` because the administrator's only security key was
disabled, the reset command it shows now reads
`python manage.py disable_instance_admin_2fa --email` followed by that
administrator's address, instead of `<your email>`, and the message shows its
title, "Security key disabled". The API adds the account's stored address to
the `5198` redirect only after the password and the administrator check have
passed, so it tells the caller nothing they did not just type. Because the
address ends up in a command an operator is asked to paste into a shell, and a
link can be crafted to carry any address, only a plain address is printed:
anything with spaces, quotes, `$`, backticks, `;`, `|`, `&`, `<`, `>` or a
leading `-` keeps the `<your email>` placeholder. The lockout itself is
unchanged; see [God Mode second factor](../god-mode-second-factor.md).

## Migrations and compatibility

**The all-in-one container stops gracefully.** On `0.2.0` the start script did
not `exec` supervisord, so the stop signal never reached it: `docker stop`
waited out its timeout, 10 seconds by default, and then killed every program.
supervisord now runs as the container's main process and stops the programs in
order: first the proxy, the workers and `live`, which stores the pages still
open while the API is still running, then the API and `space`. In testing, the
container stopped in about 4 seconds, with every program exiting cleanly.
A busy program may take up to 30 seconds, so the
[all-in-one README](../../deployments/aio/community/README.md) recommends
`docker stop -t 60`, or `docker run --stop-timeout 60`.
`supervisorctl status` now works inside the container. It connects through a
unix socket at `/run/supervisor/supervisor.sock` that only root can use;
nothing listens on a network port for it.

**On the all-in-one image, /spaces now redirects to /spaces/.** Without the
trailing slash it served the web app on `0.2.0`. It now answers with a `301` to
`/spaces/`, as Docker Compose already did.

This release adds no database or license migration compared with `0.2.0`, and
the migrations lockfile is unchanged. The Helm chart's templates, values and
Secrets do not change, and neither do the Compose and Swarm deployment files.
The all-in-one image changes only as described above.

Upgrade from `0.2.0` or `0.1.4`. The installers pick the newest stable release
on their own: run `./setup.sh upgrade` (or `swarm.sh upgrade`) with the `0.2.1`
script. Use the `v0.2.1` all-in-one image, which the `stable` tag now also
points to, or run `helm upgrade` with `--version 0.2.1` on Kubernetes. No other
operator action is required. An upgrade from `0.1.4` also brings everything
`0.2.0` changed, including the convergence with upstream Plane 1.5.0 and the
repair of real-time collaboration; read the
[`0.2.0` notes](hangar-v0.2.0.md) first. An upgrade from `0.2.0` to this
release, followed by a restore of its backup into a new installation, is tested
as part of the release.

Product version is `v0.2.1`, Git tag `hangar-v0.2.1`, Helm chart version
`0.2.1`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.2.1`.

## Known limitations and rollback

The interface is still the Plane 1.4 design: the upstream 1.5.0 Propel redesign
is not included, and whether to adopt it is still to be decided. The recorded
upstream base stays Plane 1.4.0 with the 1.4.3 changes backported. On
Kubernetes this release is qualified for evaluation on AMD64 only: the
production profile has still not completed qualification, so do not run the
chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that adds it if you
need it.

**Rolling back to `0.2.0`** needs no schema change and no change to the Helm
values: only the images change. An all-in-one installation that follows the
`stable` tag has to name `v0.2.0` to roll back, because `stable` now points to
`0.2.1`. Rolling back brings back the mistune denial of service, the
placeholder address in the `5198` reset hint, the forced kill when the
all-in-one container stops and the web app at `/spaces` there.

**Rolling back further, to `0.1.4`, brings the collaboration bug back:**
concurrent edits to one page are lost again. It needs no schema change either;
see the [`0.2.0` notes](hangar-v0.2.0.md#known-limitations-and-rollback) for
what else returns, and roll back that far only if you need to.
