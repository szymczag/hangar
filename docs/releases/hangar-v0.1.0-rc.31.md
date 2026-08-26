## Security and privacy

`rc.31` follows the first real deployment of `rc.30` and fixes what that
exercise exposed. Two of these are corrections to `rc.30` itself.

**The `rc.30` Compose asset could not pass the console second-factor settings to
the API containers.** `x-app-env` in the published `docker-compose.yml` is the
entire environment those containers receive — there is no `env_file` — and none
of `WEBAUTHN_RP_ID`, `WEBAUTHN_ALLOWED_ORIGINS`, `ADMIN_WEBAUTHN_REQUIRED` or the
`ADMIN_2FA_*` timings were listed. Since `rc.30` made the second factor
mandatory, an operator installing from those assets over `http://` lost console
access with the documented recovery switch unreachable: it existed in the code
and could not be set from the deployment path that needs it. Docker Swarm was
affected identically, because `swarm.sh` downloads the same file.

**Creating an API token required nothing but being signed in.** Any account —
a guest, or one belonging to no workspace at all — could mint a token, and the
token reached every workspace its owner belonged to. Someone who was a guest in
one workspace and an administrator of their own acted through it in the first.
A token now names the workspace it may act in, which the request layer already
knew how to confine, and minting one requires a role there at or above
`API_TOKEN_MINIMUM_ROLE`. The default is guest, which is what every member could
already do, so upgrading takes nobody's ability away until an administrator
raises it.

Enrolling an OpenPGP key no longer requires encrypted delivery to be switched on
first. The previous gate produced the failure it appeared to prevent: nobody
could hold a verified key until an administrator enabled encryption, so the first
encrypted send always went to an audience without keys — in the clear. The
challenge remains a real proof of possession while the feature is off: the mailer
encrypts any message naming a key explicitly, and refuses to send rather than
falling back to plaintext.

An instance administrator can now set the certificate an account's mail is
encrypted to, and freeze self-service for that account. This is the power to
arrange to read someone's mail — a key set this way is activated without the
challenge that proves the holder controls the private half, because the
administrator vouches for it instead. With a key escrow that is the intended
workflow; without one it is indistinguishable from surveillance. The two are
separated by evidence rather than permission: every action writes an immutable
record naming the administrator, the account, the fingerprint and the stated
reason; the account holder is emailed; and the endpoint requires the console's
WebAuthn second factor. The panel states all of this beside the field where a
certificate is pasted.

The lock is recorded against the account rather than a key, since a lock attached
to a key would be escaped by enrolling another one.

Configuration writes that cannot take effect are now refused by name rather than
reported as success. A key with no stored row was silently dropped: the answer was
`200` listing everything except the setting that did not apply.

## Migrations and compatibility

Three migrations, all additive. `license.0013_api_token_minimum_role` and
`license.0014_instance_branding` seed configuration keys.
`ext.0013_openpgp_policy` creates two tables for administrator-managed keys and
their audit records. No data backfill, and no existing row is modified.

**Existing API tokens are unaffected.** They keep `workspace = NULL` and their
previous reach — the owner's memberships. Raising `API_TOKEN_MINIMUM_ROLE`
governs minting, not tokens already issued, and nothing here revokes one. Only
tokens created from now on name a workspace.

Nine settings are now forwarded to the API containers by the Compose asset:
`ADMIN_BASE_URL`, `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME`, `WEBAUTHN_ALLOWED_ORIGINS`,
`ADMIN_WEBAUTHN_REQUIRED`, and the four `ADMIN_2FA_*` timings. Defaults match the
application's own, so behaviour is unchanged for a deployment that sets none of
them. **An instance installed from `rc.30` assets should take the new
`docker-compose.yml` and `variables.env` from this release**, because that is the
only way `ADMIN_WEBAUTHN_REQUIRED` becomes settable.

New panel-managed configuration keys: `API_TOKEN_MINIMUM_ROLE` (default `5`,
guest), `INSTANCE_BRANDING_NAME`, `INSTANCE_SIGN_IN_HEADER`,
`INSTANCE_SIGN_IN_SUBHEADER` and `INSTANCE_LOGO_ASSET_ID`. Every branding value
is optional, and empty means the built-in wording and wordmark, so an instance
that sets none looks exactly as before.

`FileAsset` gains an `INSTANCE_LOGO` entity type, served publicly by the static
asset endpoint because the sign-in page is seen before anyone has a session. It
is held to the same server-side raster validation as the other public inline
images.

One removal worth stating: the sign-in footer no longer reads "Join 10,000+ teams
building with Hangar" above the logos of Zerodha, Sony, Dolby and Accenture.
Those were inherited Plane marketing assets — companies that are not customers of
a self-hosted deployment and never agreed to appear on its sign-in page.

Panel behaviour changes without any change to what is stored: the domain policy
is edited as one row per domain instead of three hand-composed strings, Google's
authentication mode is chosen rather than typed, and callback URLs scroll instead
of overflowing. Values written by earlier versions are read and rendered
unchanged.

If the deployment sets `SKIP_ENV_VAR=0`, the panel is read-only by design and
every form refuses to save. That is now visible — the controls are disabled and
the server's reason is shown — but it remains a deployment decision, not a bug to
work around.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.31`, the chart version is `0.1.0-rc.31`, the
signed Git tag is `hangar-v0.1.0-rc.31`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.31`. `rc.30` is the immediately previous
complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, and `rc.28` were
consumed by incomplete publication attempts and are not upgrade or rollback
targets.

## Known limitations and rollback

Hangar `rc.31` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Three paths have complete automated coverage but no recorded manual
verification, and each should be exercised on a non-production instance first:
the WebAuthn flow against a hardware key in a browser, the console identity
import against a real directory export, and administrator-managed OpenPGP keys
against a real certificate.

`rc.30` is structurally compatible as a rollback target; the added tables and
configuration rows can remain in place, and no migration needs reversing. Rolling
back restores API tokens that anyone can mint and that reach every workspace
their owner belongs to, removes administrator control over OpenPGP keys, and
returns the Compose asset that cannot set `ADMIN_WEBAUTHN_REQUIRED` — so a
rollback undertaken _because_ of a console lockout would reintroduce the
condition that made it unrecoverable. Prefer a forward correction.

Tokens minted under `rc.31` name a workspace, and a rollback does not remove that
column, so they keep working and stay confined. Nothing has to be reissued in
either direction.
