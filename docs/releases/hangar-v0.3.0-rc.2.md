## Security and privacy

**The installers now keep plane.env and its copies readable by the owner only;
every earlier release left them readable by all local users.** `plane.env`
holds `SECRET_KEY`, `LIVE_SERVER_SECRET_KEY`, and the database, RabbitMQ, Redis
and S3 credentials. Up to and including `0.3.0-rc.1`, `setup.sh` (Compose) and
`swarm.sh` (Swarm) wrote `plane.env` and the copies an upgrade keeps,
`plane.env.bak` and `archive/<timestamp>.env`, with the umask's mode. That is
usually `644` or `664`, which any local user can read. The `archive/` and
`backup/` folders and the backup archives also took the umask's mode. This
release changes that:

- The installers write `plane.env`, `plane.env.bak` and `archive/*.env` with
  mode `600`, and create `archive/` with mode `700`, whatever the umask.
- A backup writes `backup/`, each dated folder and each archive for the owner
  only (`700` folders, `600` archives).
- Before every action, even a plain `start`, `setup.sh` and `swarm.sh` remove
  group and other access from what earlier releases left behind: `plane.env`,
  `plane.env.bak`, `archive/*.env`, `archive/` and `backup/`. They print one
  line naming what they changed, for example
  `NOTICE: restricted to the owner, because other local users could read them: archive plane.env plane.env.bak archive/1700000000.env`.
  Once everything is tight they print nothing.
- `restore.sh` no longer mounts the backup folder into a container. It reads
  each archive on the host and streams it into the container. A container
  cannot read owner-only archives under user-namespace remapping, so restore
  still works on such hosts.
- `setup.sh`, `swarm.sh` and `restore.sh` must now run as the user that owns
  `plane-app/`, or as root. A group member can no longer read `plane.env`
  through group permissions.

On a host where other local users had access, **treat the secrets in
`plane.env` as exposed and rotate them.** Rotate the database and RabbitMQ
passwords as described in
[Rotating the database and RabbitMQ passwords](../../deployments/cli/community/README.md#rotating-the-database-and-rabbitmq-passwords).
Replace the bundled object-storage key pair as described under
[object-storage credentials](../../deployments/cli/community/README.md#upgrading-hangar-version).
Also replace `SECRET_KEY` and `LIVE_SERVER_SECRET_KEY`. A new `SECRET_KEY`
cannot decrypt the secrets saved in God Mode: enter the SMTP password, the
OAuth and OIDC client secrets and the AI provider's API key again afterwards.
With Google Calendar capacity enabled, read
[Replacing a template SECRET_KEY with Google Calendar capacity](../../deployments/cli/community/README.md#replacing-a-template-secret_key-with-google-calendar-capacity)
first. Any copy of `plane.env` that you made by hand, for example next to a
backup, needs the same protection.

The fix reaches the stable channel with `0.3.0`. Until then, **stable `0.2.2`
installations can protect themselves by hand.** Run this from the folder that
holds `plane-app/`. A path that does not exist on your host is reported and skipped.

```bash
chmod 600 plane-app/plane.env plane-app/plane.env.bak plane-app/archive/*.env
chmod 700 plane-app/archive plane-app/backup
```

An upgrade with the `0.2.2` script replaces `plane.env` again at the umask's
mode, so repeat the commands after every upgrade until you run `0.3.0`.

**The object-storage migration no longer puts S3 keys on container command
lines.** `migrate-object-storage.sh` passed the old and the new S3 key pairs to
`docker run` as `-e NAME=value`. Every local user could read them with `ps` or
in `/proc` while the migration ran. Each container now gets the variable name
only, and its value comes from that one command's environment. The README's
database password rotation also no longer puts the new password on the
`psql` command line.

The all-in-one image and the Helm chart are not affected. The all-in-one image
already wrote its `secrets.env` and `plane.env` for the owner only. On
Kubernetes the secrets are Kubernetes Secrets.

**God Mode moves to the new upstream 1.5.0 design, with its security rules
kept.** This carries over from `0.3.0-rc.1`. The instance admin console at
`/god-mode/` now uses the Propel component library from upstream Plane
`v1.5.0`: its sidebar, page layout, fields, switches, selects and banners.
Hangar's own screens move with it: users and OpenPGP, OIDC, SAML, domain
policy, identity import, branding, maintenance, the email delivery log, and the
second-factor sign-in and enrolment. What the console enforces does not change,
or gets stricter:

- God Mode secrets stay write-only. The OAuth and OIDC client secrets, the SMTP
  password and the AI provider's API key are never shown and never filled back
  in. A secret field always opens empty; leaving it blank keeps the stored
  secret, and it is emptied again after a save. The AI provider's API key is
  now required while none is stored, as the client secrets already were. See
  [federated SSO security](../federated-sso-security.md).
- Telemetry stays off by default in the setup form, and the password rules are
  unchanged: at least 15 characters and a strong enough strength estimate.
- There is still no Unsplash image page and no external image provider.
- The second-factor lockout messages, including the reset command and the
  administrator's address, are unchanged.
- The console's Content-Security-Policy and Trusted Types enforcement do not
  change: no new inline script or style hash and no new exception. The new
  components bring in Base UI 1.8.0, whose one inline style matches the hash
  that is already allowed.

**God Mode secret fields no longer take a browser's saved password.** The
secret inputs carried no autofill hint, so a browser could fill a saved login
password into an empty SMTP password, client secret or API key field, and the
next save would replace the stored secret with it. They are now marked as new
passwords, which browsers do not fill with a saved login. The console sign-in
and the identity import re-authentication are real logins and keep their hints.

**God Mode sign-in and setup wait for their CSRF token.** The submit button
stays disabled until the console has fetched the token, so a quick submit can
no longer be sent without one and refused.

**Hangar builds the Propel component library from its own source.** Upstream
publishes `@makeplane/propel` 0.9.7 (AGPL-3.0) to npm only as compiled output.
Hangar recovered its source from the published package into
`packages/makeplane-propel`, checked against the package's pinned integrity, and
builds it with its own toolchain; CI checks that the build matches the
published package. This source is the Corresponding Source for the Propel code
in God Mode. A new security invariant makes every Hangar package take Propel
from that workspace copy, never from the registry. `@plane/blocks` is taken
from upstream `v1.5.0` with Hangar's password-strength rules.

## Migrations and compatibility

**God Mode fixes from testing `0.3.0-rc.1`.** These are new in this candidate:

- Toasts sat in the bottom-left corner, and the close button of toasts and
  dialogs covered their icon. The Propel components use Tailwind utilities that
  Tailwind 4.1 did not know and dropped without a warning. Tailwind moves to
  4.2.4, the version upstream `v1.5.0` uses, and a build test now fails when the
  admin stylesheet lacks a class that a Propel component uses.
- A React hydration error (#418) appeared on every load of God Mode after the
  first. The prerendered page now carries the loading screen that the first
  client render shows.
- Callback, ACS and metadata URLs wrapped in the middle of a word. They now
  break after a path separator. The copy button still copies the whole value.
- The "security key disabled" message showed as information. It now shows as
  an error.
- On the Users page, "Manage key" is a proper button with a key icon, and the
  OpenPGP key panel opens in its own row, so it no longer squeezes the columns.
- On the AI page the API key field was narrow. It is now as wide as the model
  field and shows its whole placeholder.
- The OAuth provider pages said "sign up to plane". They now say "log in or
  sign up for Hangar", and the SAML and OIDC pages say "Hangar-provided details
  for your IdP" again. The branding check now also catches the lower-case
  product name.

**Tailwind 4.2.4 does not change how the web app or Spaces look.** Their
stylesheets gain about twenty rules, mostly for the logical inset utilities
that the Propel components use, and `rotate-0` now writes `rotate: 0deg`
instead of `rotate: none`, which looks the same. Their application code does
not change, and no visual-regression story of the web app or Spaces changed.

**Apart from that, nothing changes in the web app, Spaces, the API or the live
server.** The web app and Spaces keep the current Plane 1.4 design; only God
Mode moves to the new one in this candidate, as a pilot for adopting the
redesign everywhere. The `api`, `web`, `space` and `live` application code is
unchanged apart from shared helpers God Mode now uses, which do not change
their output. The in-app release notes in the web app name this release.

**No database migration and no chart change.** This release adds no database
or license migration compared with `0.2.2` or `0.3.0-rc.1`, and the migrations
lockfile is unchanged. The Helm chart's templates, values and Secrets do not
change, and neither do the Compose and Swarm deployment files. The installer
scripts `setup.sh`, `swarm.sh`, `restore.sh` and `migrate-object-storage.sh`
change as described above. The God Mode image keeps its nginx server,
Content-Security-Policy and headers.

Upgrade from `0.2.2` or `0.3.0-rc.1`. This is a release candidate, so the
installers do not pick it on their own: run
`HANGAR_RELEASE=v0.3.0-rc.2 ./setup.sh upgrade` (or `swarm.sh`) with the
`0.3.0-rc.2` script, use the `v0.3.0-rc.2` all-in-one image, or run
`helm upgrade` with `--version 0.3.0-rc.2` on Kubernetes. The new script
tightens the files described above on its first run and prints the NOTICE. Run
it as the owner of `plane-app/` or as root. No other operator action is
required. Reload open God Mode tabs after the upgrade.

Product version is `v0.3.0-rc.2`, Git tag `hangar-v0.3.0-rc.2`, Helm chart
version `0.3.0-rc.2`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.3.0-rc.2`.

## Known limitations and rollback

This is a release candidate for `0.3.0`. `0.2.2` stays the current stable
release, and the installers keep choosing it unless you name this release.
`0.3.0-rc.1` is superseded by this candidate: do not install it, and upgrade
an installation on it to `0.3.0-rc.2`.

Only God Mode has the new design. The web app and Spaces keep the Plane 1.4
design until the redesign is adopted there too. The recorded upstream base
stays Plane 1.4.0 with the 1.4.3 changes backported. On Kubernetes this release
is qualified for evaluation on AMD64 only: the production profile has still not
completed qualification, so do not run the chart in production yet. The
all-in-one image does not send `Strict-Transport-Security` itself; put it
behind a proxy that adds it if you need it.

**Rolling back to `0.2.2`** needs no schema change and no change to the Helm
values: only the images change. It brings back the previous God Mode look, and
the secret fields that a browser could fill with a saved password. The files
this release tightened keep their modes, but the next upgrade with the `0.2.2`
script writes `plane.env` at the umask's mode again; protect it with the
commands above.
