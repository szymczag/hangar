## Security and privacy

**God Mode moves to the new upstream 1.5.0 design, with its security rules
kept.** The instance admin console at `/god-mode/` now uses the Propel
component library from upstream Plane `v1.5.0`: its sidebar, page layout,
fields, switches, selects and banners. Hangar's own screens move with it: users
and OpenPGP, OIDC, SAML, domain policy, identity import, branding, maintenance,
the email delivery log, and the second-factor sign-in and enrolment. What the
console enforces does not change, or gets stricter:

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

**Nothing changes in the web app, Spaces, the API or the live server.** The
web app and Spaces keep the current Plane 1.4 design; only God Mode moves to
the new one in this candidate, as a pilot for adopting the redesign
everywhere. The `api`, `web`, `space` and `live` application code is unchanged
apart from shared helpers God Mode now uses, which do not change their output.
The in-app release notes in the web app name this release.

**No database migration and no chart change.** This release adds no database
or license migration compared with `0.2.2`, and the migrations lockfile is
unchanged. The Helm chart's templates, values and Secrets do not change, and
neither do the Compose and Swarm deployment files. The God Mode image keeps its
nginx server, Content-Security-Policy and headers.

Upgrade from `0.2.2`. This is a release candidate, so the installers do not
pick it on their own: run `HANGAR_RELEASE=v0.3.0-rc.1 ./setup.sh upgrade` (or
`swarm.sh`) with the `0.3.0-rc.1` script, use the `v0.3.0-rc.1` all-in-one
image, or run `helm upgrade` with `--version 0.3.0-rc.1` on Kubernetes. No other
operator action is required. Reload open God Mode tabs after the upgrade.

Product version is `v0.3.0-rc.1`, Git tag `hangar-v0.3.0-rc.1`, Helm chart
version `0.3.0-rc.1`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.3.0-rc.1`.

## Known limitations and rollback

This is a release candidate for `0.3.0`. `0.2.2` stays the current stable
release, and the installers keep choosing it unless you name this release.

Only God Mode has the new design. The web app and Spaces keep the Plane 1.4
design until the redesign is adopted there too. The recorded upstream base
stays Plane 1.4.0 with the 1.4.3 changes backported. On Kubernetes this release
is qualified for evaluation on AMD64 only: the production profile has still not
completed qualification, so do not run the chart in production yet. The
all-in-one image does not send `Strict-Transport-Security` itself; put it
behind a proxy that adds it if you need it.

**Rolling back to `0.2.2`** needs no schema change and no change to the Helm
values: only the images change. It brings back the previous God Mode look, and
the secret fields that a browser could fill with a saved password.
