## Security and privacy

`rc.30` is a security release. It closes a federated sign-in boundary, hardens
the God Mode console, and fixes authorization defects found by probing the
deployed route surface rather than by reading code.

The instance-admin console now requires a WebAuthn second factor. The password
step no longer creates a logged-in session: it leaves the caller anonymous and
issues a pending state, so the console is closed by construction rather than by
a check a later refactor could omit. `InstanceAdminPermission` additionally
requires a session marker proving the second factor, which makes "this session
proved a security key" an invariant every present and future path creating a
console session must satisfy. Keys are non-resident with user verification
preferred — a second factor, not a passkey; the password remains required.
Challenges are single-use through a conditional update, bound to the issuing
session, and expire. Signature-counter regression is treated as cloning only
when the stored counter is above zero, because many authenticators always report
zero. Every cryptographic failure returns one error code, so the endpoint is not
an oracle distinguishing an unknown credential from a bad signature.

God Mode sign-in previously had no rate limiting at all; password guessing was
bounded only by request throughput. It is now throttled.

Email domains can be pinned to designated federated providers
(`SSO_ENFORCED_DOMAINS`). A pinned domain refuses password sign-in, magic codes,
and every provider not named for it, on both sign-up and sign-in, so nobody can
claim a colleague's address through a weaker route. Matching is exact and
IDNA-folded; an entry naming only unknown providers fails closed rather than
admitting everything.

Every OAuth and OIDC destination now goes through one validated outbound
transport. Destinations are resolved once, validated, and pinned to the resolved
address, and the connected peer is re-checked against it, which defeats DNS
rebinding between validation and connection. Non-public addresses are refused
unless an operator allowlists them explicitly for self-managed GitLab or Gitea;
redirects are refused rather than followed; responses are capped; and OIDC pins
TLS 1.3 exactly while OAuth permits 1.2 for self-managed hosts. Provider network
allowlists are deployment-owned and cannot be set from the panel, because they
permit credential-bearing requests into internal networks.

Authorization defects closed in this release, each found by an automated probe
and each proven by a test before it was fixed:

- any authenticated user could create views in any workspace, including
  workspace-visible ones, without membership;
- analytics returned counts for projects in other workspaces, and accepted
  project IDs from the client without checking they belonged to the caller's
  workspace;
- archiving a project required only workspace membership, because the permission
  class answers `POST` from a branch written for _creating_ a project;
- a `PATCH` on an API token returned the token secret in plain text, while `GET`
  correctly withheld it;
- workspace logos and project covers were readable by unauthenticated callers
  from any instance by ID; user avatars and covers remain public deliberately;
- a member listing included deactivated accounts.

The federated identity import gained a refusal that the CLI never made. It
checked only that a subject was not already owned by another account, never the
reverse: an account already signing in through an issuer could be given a second,
different subject. Sign-in resolves an identity by binding key and logs in
whoever it names, and nothing constrains `(user, provider, issuer)`, so the
second identity did not replace the first — it added an independent way into the
account while the original kept working, invisible to the owner. Both the CLI and
the new console upload now refuse it.

That import is now available in the console for operators without shell access.
It is guarded more heavily than the CLI because it is reachable over the network:
the second factor gates the endpoint, and confirming requires the password
re-entered at the point of use. The file is uploaded once to preview and again to
confirm, never held server-side in between, and a signed grant carrying the
file's SHA-256 digest and naming the issuing admin binds the two steps — so the
file that is applied is provably the file that was reviewed.

Refusals from the identity import carry a code, and the wording returned to the
caller is looked up from a fixed table rather than rendered from the exception
that raised it. Several of those refusals chain from a library error, so
rendering them would carry that error's text — and whatever a later change
interpolates into it — into an HTTP response.

The `nanoid` override was raised past CVE-2026-67213.

## Migrations and compatibility

**Every existing God Mode session is invalidated by this release, and every
instance administrator must enroll a security key at their next sign-in.** This
is intended: sessions created before the second factor existed cannot have
proved one. Plan the upgrade for a moment when an administrator with a key
present can complete enrollment.

**An instance served over `http://` on anything other than localhost cannot use
the console at all after this upgrade.** WebAuthn requires a secure context, and
the second factor is mandatory. Deployments without TLS must obtain it before
upgrading, or set `ADMIN_WEBAUTHN_REQUIRED=0` — which exists to recover a locked
instance, not to run without the factor.

If the console is served from a different host than the web application, set
`WEBAUTHN_RP_ID` to their common parent (`example.com` for `admin.example.com`
and `app.example.com`). A relying-party ID that is not a parent of the console
origin is rejected by the browser before the request is made, and because the
factor is mandatory, the symptom is not a broken second factor but permanent
loss of console access for every administrator. Configuration that would produce
this is refused with a named error instead of issuing options. The server pins
expected origins to an explicit list regardless.

Four migrations: `ext.0012_admin_webauthn` creates the credential and challenge
tables; `license.0010_sso_enforced_domains`, `license.0011_sso_auto_join_workspaces`,
and `license.0012_sso_auto_join_projects` seed configuration keys. All are
additive. No data backfill is required and no existing row is modified.

New environment variables, all optional with defaults: `WEBAUTHN_RP_ID`,
`WEBAUTHN_RP_NAME`, `WEBAUTHN_ALLOWED_ORIGINS`, `ADMIN_WEBAUTHN_REQUIRED`
(default on), `ADMIN_2FA_PENDING_ASSERT_WINDOW`, `ADMIN_2FA_PENDING_ENROLL_WINDOW`,
`ADMIN_2FA_CHALLENGE_TTL`, and `ADMIN_2FA_MAX_ATTEMPTS`. New panel-managed
configuration keys: `SSO_ENFORCED_DOMAINS`, `SSO_AUTO_JOIN_WORKSPACES`, and
`SSO_AUTO_JOIN_PROJECTS`. Panel-managed settings take effect only when
`SKIP_ENV_VAR` is at its default; the configuration endpoint now reports which
source is authoritative and refuses writes that could never take effect, instead
of reporting success for a change nothing will read.

`manage.py disable_instance_admin_2fa --email` recovers an administrator who has
lost their key. It writes directly rather than going through the soft-delete
path, so it works when the Celery broker is down, and it invalidates that
administrator's live sessions by default.

Behavior change to an existing tool: `manage.py import_federated_identities` now
refuses a file that would give an already-federated account a second subject at
the same issuer (`ACCOUNT_ALREADY_FEDERATED`). A script that relied on adding a
second subject will stop working. Re-importing an identical file remains a
no-op.

Pinning a domain removes password and magic-link sign-in for it. Import identity
mappings and verify sign-in for representative accounts **before** setting
`SSO_ENFORCED_DOMAINS`, and keep a break-glass administrator outside the pinned
domain.

There is no new Helm value, Secret, Kubernetes resource, public route, storage,
RBAC, or `NetworkPolicy` change. Deploy all application images as one Helm
revision and wait for the revision-scoped migration Job before admitting
traffic. Do not operate mixed `rc.29` and `rc.30` web/API revisions: the console
sign-in contract changed on both sides.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The qualification boundary
remains Kubernetes 1.30 through 1.36 (including 1.36.2), Helm 4.2,
`linux/amd64`, Restricted Pod Security Admission, TLS ingress with WebSocket
support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.30`, the chart version is `0.1.0-rc.30`, the
signed Git tag is `hangar-v0.1.0-rc.30`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.30`. `rc.29` is the immediately
previous complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, and
`rc.28` were consumed by incomplete publication attempts and are not upgrade or
rollback targets.

## Known limitations and rollback

Hangar `rc.30` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Two paths in this release have complete automated coverage but no recorded
manual verification, and both should be exercised on a non-production instance
first. The WebAuthn flow is verified end to end against a software authenticator
producing real ES256 signatures — which did find a defect in clone detection —
but not against a hardware key in a browser. The console identity import is
covered by contract tests but has not been run against a real directory export.

`rc.29` is structurally compatible as an emergency technical rollback target;
the added tables and configuration rows can remain in place. Rolling back
restores a God Mode console with no second factor and no rate limiting, removes
domain pinning enforcement, and reopens the authorization defects listed above,
so there is no security-equivalent rollback target. Prefer a forward correction.
If availability recovery requires rollback, move every application component
together and return to `rc.30` promptly. Restore a database backup only when
unrelated writes, corruption, or the incident requires point-in-time recovery.

A locked-out console does not require rollback: set `ADMIN_WEBAUTHN_REQUIRED=0`
to restore access, or clear one administrator's enrollment with
`manage.py disable_instance_admin_2fa --email`.
