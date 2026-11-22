## Security and privacy

**The installers now keep plane.env and its copies readable by the owner only;
every earlier release left them readable by all local users.** `plane.env`
holds `SECRET_KEY`, `LIVE_SERVER_SECRET_KEY`, and the database, RabbitMQ, Redis
and S3 credentials. Up to and including `0.2.2`, `setup.sh` (Compose) and
`swarm.sh` (Swarm) wrote `plane.env` and the copies an upgrade keeps,
`plane.env.bak` and `archive/<timestamp>.env`, with the umask's mode. That is
usually `644` or `664`, which any local user can read. The `archive/` and
`backup/` folders and the backup archives also took the umask's mode.

> [!IMPORTANT]
> **Download this release's `setup.sh` before you upgrade.** The protection is
> in the script, and the script does not update itself. `./setup.sh upgrade`
> fetches the new release's `docker-compose.yml`, `variables.env` and
> `migrate-object-storage.sh` (Swarm: `docker-compose.yml` and `variables.env`),
> but it never downloads a new `setup.sh`, `swarm.sh` or `restore.sh` and never
> restarts itself with one. An upgrade run with the `0.2.2` script, which picks
> `0.3.0` on its own, installs the new images and leaves `plane.env` and
> `plane.env.bak` readable by others: on a test install upgraded with an older
> script they stayed at mode `664`. So:
>
> 1. Download this release's `setup.sh` (or `swarm.sh`, saved as `setup.sh`),
>    as described under [Upgrade](#migrations-and-compatibility) below.
> 2. Run `./setup.sh upgrade` with it.
> 3. Check the result: `stat -c '%a' plane-app/plane.env` (`stat -f '%Lp'` on
>    macOS) prints `600`. The new script prints a
>    `NOTICE: restricted to the owner, ...` line on its first run, whichever
>    action that is, when it tightens anything; once everything is tight it
>    prints nothing.
>
> If you already upgraded with an older script, download this release's script
> and run any action with it, for example `./setup.sh start` (Swarm:
> `./setup.sh status`). That run prints the NOTICE and tightens the files.

What the new scripts do:

- They write `plane.env`, `plane.env.bak` and `archive/*.env` with mode `600`,
  and create `archive/` with mode `700`, whatever the umask.
- A backup writes `backup/`, each dated folder and each archive for the owner
  only (`700` folders, `600` archives).
- Before every action, even a plain `start`, `setup.sh` and `swarm.sh` remove
  group and other access from what earlier releases left behind: `plane.env`,
  `plane.env.bak`, `archive/*.env`, `archive/` and `backup/`. They print one
  line naming what they changed, for example
  `NOTICE: restricted to the owner, because other local users could read them: archive plane.env plane.env.bak archive/1700000000.env`.
- `restore.sh` no longer mounts the backup folder into a container. It reads
  each archive on the host and streams it into the container. A container
  cannot read owner-only archives under user-namespace remapping, so restore
  still works on such hosts. Use this release's `restore.sh` to restore a
  backup made by this release.
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

If you cannot upgrade right away, protect a `0.2.2` installation by hand. Run
this from the folder that holds `plane-app/`. A path that does not exist on
your host is reported and skipped.

```bash
chmod 600 plane-app/plane.env plane-app/plane.env.bak plane-app/archive/*.env
chmod 700 plane-app/archive plane-app/backup
```

An install or upgrade run with the `0.2.2` script writes `plane.env` again at
the umask's mode, so repeat the commands after each one.

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
kept.** The instance admin console at `/god-mode/` now uses the Propel
component library from upstream Plane `v1.5.0`: its sidebar, page layout,
fields, switches, selects and banners. Hangar's own screens move with it:
users and OpenPGP, OIDC, SAML, domain policy, identity import, branding,
maintenance, the email delivery log, and the second-factor sign-in and
enrolment. What the console enforces does not change, or gets stricter:

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

**God Mode fixes found while testing the release candidates.** Testing
`0.3.0-rc.1` found these in the new design; they are fixed in this release:

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
  for your IdP". The branding check now also catches the lower-case product
  name.

**Tailwind 4.2.4 does not change how the web app or Spaces look.** Their
stylesheets gain about twenty rules, mostly for the logical inset utilities
that the Propel components use, and `rotate-0` now writes `rotate: 0deg`
instead of `rotate: none`, which looks the same. Their application code does
not change, and no visual-regression story of the web app or Spaces changed.

**Only God Mode is redesigned; the web app and Spaces are unchanged.** The web
app and Spaces keep the current Plane 1.4 design; only God Mode moves to the
new one, as a pilot for adopting the redesign everywhere. The `api`, `web`,
`space` and `live` application code is unchanged apart from shared helpers God
Mode now uses, which do not change their output. The in-app release notes in
the web app name this release.

**No database migration and no chart change.** This release adds no database
or license migration compared with `0.2.2`, and the migrations lockfile is
unchanged. The Helm chart's templates, values and Secrets do not change, and
neither do the Compose and Swarm deployment files. The installer scripts
`setup.sh`, `swarm.sh`, `restore.sh` and `migrate-object-storage.sh` change as
described above. The God Mode image keeps its nginx server,
Content-Security-Policy and headers.

Upgrade from `0.2.2`. The installers pick `0.3.0` on their own, but only this
release's script protects `plane.env`, so on Compose and Swarm:

1. Download the `0.3.0` script next to `plane-app/`, replacing the old one:
   `curl -fsSL -o setup.sh https://github.com/szymczag/hangar/releases/download/hangar-v0.3.0/setup.sh`
   (Swarm: the same release's `swarm.sh`, saved as `setup.sh`), then
   `chmod +x setup.sh`. Check it as described in the installation guide's
   [How `setup.sh` verifies what it downloads](../../deployments/cli/community/README.md#how-setupsh-verifies-what-it-downloads).
2. Run `./setup.sh upgrade`, as the owner of `plane-app/` or as root.
3. Confirm that `stat -c '%a' plane-app/plane.env` prints `600`. The upgrade
   run prints the NOTICE described above when it tightened anything.

Use the `v0.3.0` all-in-one image, which the `stable` tag now also points to,
or run `helm upgrade` with `--version 0.3.0` on Kubernetes. No other operator
action is required. Reload open God Mode tabs after the upgrade. An
installation on `0.3.0-rc.1` or `0.3.0-rc.2` upgrades the same way; `0.3.0` is
built from the `0.3.0-rc.2` source plus its release notes and version. An
upgrade from `0.2.2` to this release, followed by a restore of its backup into
a new installation, is tested as part of the release. Upgrading from a release
older than `0.2.2` also brings what the [`0.2.2` notes](hangar-v0.2.2.md) and
the releases before it describe; read them first.

Product version is `v0.3.0`, Git tag `hangar-v0.3.0`, Helm chart version
`0.3.0`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.3.0`.

## Known limitations and rollback

`0.3.0-rc.1` and `0.3.0-rc.2` were release candidates for this release and are
superseded by it; do not install them. The previous stable release, for
upgrades and rollback, is `0.2.2`.

Besides the automated tests, both candidates were tested on a real Docker
Compose installation. The upgrades ran no migrations and left the data
fingerprint identical. The God Mode secrets were checked to be write-only in
seven forms, down to the values stored in the database. The second-factor
lockout after a cloned security key worked, the console reported no
Content-Security-Policy violation, and the installer permission fix was
confirmed on `0.3.0-rc.2`. That test also found that an upgrade run with the
old script leaves `plane.env` readable by others, as described above. The
release pipeline additionally qualifies the Compose upgrade from `0.2.2` before
it publishes this release. Kubernetes was not installed on a cluster, so on
Kubernetes this release stays qualified for evaluation on AMD64 only, as
before.

Only God Mode has the new design. The web app and Spaces keep the Plane 1.4
design until the redesign is adopted there too. The recorded upstream base
stays Plane 1.4.0 with the 1.4.3 changes backported. On Kubernetes the
production profile has still not completed qualification, so do not run the
chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that adds it if you
need it.

**Rolling back to `0.2.2`** needs no schema change and no change to the Helm
values: only the images change. An all-in-one installation that follows the
`stable` tag has to name `v0.2.2` to roll back, because `stable` now points to
`0.3.0`. Rolling back brings back the previous God Mode look, and the secret
fields that a browser could fill with a saved password. The files this release
tightened keep their modes, but an install or upgrade run with the `0.2.2`
script writes `plane.env` at the umask's mode again; protect it with the
`chmod` commands above.
