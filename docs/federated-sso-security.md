# Federated SSO security and migration

Status: operator security and migration guide for OAuth, OpenID Connect, and SAML 2.0.

Last reviewed: 2026-07-14.

This guide is for self-hosted Hangar administrators and security engineers. It
explains the federated identity boundary, shows how to configure stable provider
identifiers, and provides a fail-closed migration procedure for existing users.
It does not cover identity-provider enrollment, group provisioning, SCIM, or
generic Django authentication administration.

Keep at least one tested local administrator account while changing SSO. Do not
disable the local recovery path until the new provider has passed a controlled
sign-in test.

## Security model

Hangar binds a federated account to this immutable tuple:

```text
provider + issuer + subject format + subject
```

The database stores a length-framed SHA-256 key for that tuple and enforces its
global uniqueness. The user, provider, issuer, subject format, and subject cannot
be changed after the binding is created. A changing email address updates profile
metadata; it does not transfer the binding to another user.

Email is an asserted attribute, not an account identifier. Hangar requires a
verified email from Google and OIDC. SAML attributes are accepted only after the
signed assertion, issuer, audience, destination, request correlation, time window,
and replay checks pass. If a new federated identity presents the email of an
existing local user, Hangar fails with `SSO_ACCOUNT_LINK_REQUIRED`; it never links
the account by email automatically.

| Provider | Issuer                             | Subject                                               | Subject format                                   |
| -------- | ---------------------------------- | ----------------------------------------------------- | ------------------------------------------------ |
| Google   | `https://accounts.google.com`      | ID-token `sub`                                        | Empty                                            |
| OIDC     | Exact configured/discovered issuer | Validated ID-token `sub`                              | Empty                                            |
| SAML     | Configured IdP entity ID           | Configured stable subject attribute, otherwise NameID | `attribute:<name>` or the asserted NameID format |

Transient SAML NameIDs are rejected. Use a persistent, non-reassigned identifier.
Do not use email as `SAML_ATTR_SUBJECT` unless the IdP contract guarantees that the
value is immutable and never reassigned.

### Login and invitation behavior

- New federated sign-up requires the instance sign-up policy or one active
  invitation for the asserted email.
- Invitations expire, can be revoked, and authorize sign-up and membership only
  once. The migration gives legacy pending invitations a seven-day expiry.
- Deactivated users and bot users cannot authenticate through federated SSO.
- Conflicting bindings and concurrent unique-key races fail closed and roll back
  user, invitation, token, and identity changes together.
- Profile synchronization and avatar downloads happen after the identity
  transaction and cannot change account ownership.

## Configuration reference

Configuration can be supplied through the instance administration UI or through
environment variables during initial instance configuration. Client secrets are
stored as encrypted instance configuration. Restart behavior depends on how the
deployment applies environment and instance settings; use a normal rollout after
changing deployment secrets.

### Where settings are read from

By default (`SKIP_ENV_VAR` unset, or `1`) the **stored configuration is
authoritative** and an environment variable only supplies the initial value for a
key that is not stored yet. Editing a setting in the administration UI therefore
takes effect, and a stale environment variable of the same name does not override
it after a restart.

If the deployment sets `SKIP_ENV_VAR=0`, that reverses: values are read from the
environment and stored configuration is ignored. Because every form in the
administration UI would otherwise still render and still submit, in that mode the
configuration API refuses writes with `409 Conflict` and the UI shows a banner
explaining that the deployment owns these settings. The current mode is reported
to the UI as a read-only `CONFIGURATION_SOURCE` entry (`database` or
`environment`); it cannot be set through the API.

A small number of settings are deliberately environment-only regardless of this
mode — see the egress policy below.

### Domain policy

These govern which provider owns an email domain and where its users land. Both
are editable in the administration UI under **Authentication → Domain policy**.

| Setting                    | Meaning                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------- |
| `SSO_ENFORCED_DOMAINS`     | Domains pinned to a provider, as `corp.com=google`, `corp.com=oidc;saml`, or a bare `corp.com` |
| `SSO_AUTO_JOIN_WORKSPACES` | Workspaces joined on sign-in, as `corp.com=workspace-slug:role`                              |
| `SSO_AUTO_JOIN_PROJECTS`   | Projects joined on sign-in, as `corp.com=workspace-slug/IDENTIFIER:role`                     |

A listed domain may be asserted **only** by the providers named for it. Every other
enabled method — password, magic code, and the remaining providers — is refused for
that domain on both sign-up and sign-in. This is what prevents an attacker from
claiming a colleague's address through a weaker route before its owner first signs
in, and what makes a rogue identity provider asserting the same addresses useless.
A bare domain entry admits any federated provider (`google`, `oidc`, `saml`) and
refuses credential sign-in. Matching is exact and IDNA-normalized: a parent entry
does not cover its subdomains, so list those separately.

Auto-join adds a user to the named workspace on **every** sign-in, not only at
signup, so adding a domain later also covers people who already have an account.
The role is `admin`, `member`, or `guest`, defaulting to `guest` when omitted so
that an unstated role cannot grant write access; an unrecognized role is skipped
rather than guessed. An existing membership is never modified, so a role an
administrator lowered by hand is not restored at the next sign-in and a deactivated
member is not silently reactivated.

Auto-join only applies to domains that `SSO_ENFORCED_DOMAINS` pins. Membership is
granted on the strength of an email domain, so that domain must first belong to a
designated provider; without the pin, any other enabled sign-in method would become
a route into the workspace.

Project auto-join uses the project **identifier** — the short code shown on its work
items — rather than a uuid, because that is what an operator has in front of them.
It requires the matching workspace entry: a project membership without a workspace
membership is a state the rest of the model does not expect, so an entry whose
workspace the user has not joined is skipped rather than manufacturing the workspace
seat. Archived projects are skipped, and as with workspaces an existing membership is
never modified.

```
SSO_ENFORCED_DOMAINS=corp.com=google
SSO_AUTO_JOIN_WORKSPACES=corp.com=engineering:member
SSO_AUTO_JOIN_PROJECTS=corp.com=engineering/PLAT:member
```

Both settings are editable in the administration UI under
**Authentication → Domain policy**.

Note that Google's `hd` claim is tenant-wide. Workspace mode admits every account in
an allowed hosted domain; Google issues no organizational-unit or group claim, so
finer restriction is not available from the token.

### Google

| Setting                    | Required          | Meaning                                                                                       |
| -------------------------- | ----------------- | --------------------------------------------------------------------------------------------- |
| `GOOGLE_CLIENT_ID`         | Yes               | OAuth client audience accepted by Hangar                                                      |
| `GOOGLE_CLIENT_SECRET`     | Yes               | OAuth client credential; keep in the deployment secret                                        |
| `GOOGLE_AUTH_MODE`         | Yes               | `generic` permits any validated Google account; `workspace` requires an allowed hosted domain |
| `GOOGLE_WORKSPACE_DOMAINS` | In workspace mode | Comma-separated, normalized Google Workspace hosted domains                                   |
| `ENABLE_GOOGLE_SYNC`       | No                | Synchronizes non-binding profile data for existing users                                      |

Workspace mode validates the signed Google `hd` claim. A matching email suffix is
not sufficient. Configure every intended tenant explicitly before switching from
`generic` to `workspace`.

### Self-hosted provider egress policy (Gitea, GitLab)

`GITEA_HOST` and `GITLAB_HOST` must be HTTPS origins in production. Every outbound
authentication request — token exchange, profile lookup, and for OIDC also discovery
and JWKS — resolves the destination once, rejects any answer that is not a public
address, pins the connection to a validated address, and re-checks the connected
peer against it. That last check is what defeats DNS rebinding: a hostname that
re-resolves to an internal address between validation and connection is refused at
the socket. Redirects are not followed, response bodies are capped, and every
request carries a deadline. The OAuth client secret and bearer token therefore
cannot be redirected to an administrator-selected internal service.

For an intentionally private deployment, the operator must name it explicitly in the
deployment environment:

| Setting                                            | Meaning                              |
| -------------------------------------------------- | ------------------------------------ |
| `GITEA_ALLOWED_HOSTS` / `GITLAB_ALLOWED_HOSTS`     | Comma-separated normalized DNS names |
| `GITEA_ALLOWED_IPS` / `GITLAB_ALLOWED_IPS`         | Comma-separated addresses or CIDRs   |

**These allowlists are environment-only by design and cannot be set from the
administration UI**, even when the instance otherwise reads its configuration from
the database. They permit credential-bearing outbound requests to reach private
addresses, so they belong to whoever controls the deployment rather than to anyone
holding administrator access to the panel; the configuration API rejects attempts to
set them with `400`. Changing `GITEA_HOST` or `GITLAB_HOST` in the administration UI
cannot expand the network boundary on its own. The administration UI shows this
explanation on the Gitea and GitLab pages so the constraint is discoverable at the
point of use.

Allowlisting only widens which addresses are acceptable. Address pinning and the
connected-peer check still apply to an allowlisted destination. Keep exceptions
narrow and restart the API after changing them.

### OpenID Connect

| Setting              | Required | Meaning                                                             |
| -------------------- | -------- | ------------------------------------------------------------------- |
| `IS_OIDC_ENABLED`    | Yes      | Enables the provider after configuration and migration are complete |
| `OIDC_ISSUER`        | Yes      | Exact issuer used for discovery and identity binding                |
| `OIDC_CLIENT_ID`     | Yes      | Required token audience                                             |
| `OIDC_CLIENT_SECRET` | Yes      | Client credential; keep in the deployment secret                    |
| `OIDC_PROVIDER_NAME` | No       | User-facing label; defaults to `OIDC`                               |

OIDC discovery, token, JWKS, and userinfo calls require certificate-verified TLS
1.3, public destinations, DNS-to-connection pinning, bounded responses, and no
redirects. The ID token must contain the expected issuer, audience, subject,
expiry, issue time, and nonce. Userinfo, when needed, must return the same subject.
The removed `OIDC_ALLOW_UNVERIFIED_EMAIL` setting is not supported.

### SAML 2.0

| Setting                | Required          | Meaning                                                             |
| ---------------------- | ----------------- | ------------------------------------------------------------------- |
| `IS_SAML_ENABLED`      | Yes               | Enables the provider after configuration and migration are complete |
| `SAML_IDP_ENTITY_ID`   | Yes               | Exact issuer and identity-binding scope                             |
| `SAML_IDP_SSO_URL`     | Yes               | HTTPS HTTP-Redirect SSO endpoint                                    |
| `SAML_IDP_CERTIFICATE` | Yes               | IdP assertion-signing certificate in PEM form                       |
| `SAML_PROVIDER_NAME`   | No                | User-facing label; defaults to `SAML`                               |
| `SAML_ATTR_SUBJECT`    | Recommended       | Stable, persistent subject attribute; NameID is used when empty     |
| `SAML_ATTR_EMAIL`      | Provider-specific | Email attribute override                                            |
| `SAML_ATTR_FIRST_NAME` | No                | Given-name attribute override                                       |
| `SAML_ATTR_LAST_NAME`  | No                | Family-name attribute override                                      |

Changing the IdP entity ID, OIDC issuer, or SAML subject mapping creates a new
identity namespace. Treat such a change as a migration, not ordinary profile
configuration.

## Pinning an existing domain to Google

An instance that already has accounts at the domain has two populations, and they
behave differently on the first Google sign-in after the cutover:

| Existing account                      | First Google sign-in                                     |
| ------------------------------------- | -------------------------------------------------------- |
| Has signed in with Google before       | Adopted automatically; same user id, memberships intact  |
| Only ever used a password or magic link | Refused with `SSO_ACCOUNT_LINK_REQUIRED` until linked    |

The second case is a lockout, not a corner case: the address is already held by an
unlinked user, and the refusal is deliberate — silently binding a Google subject to
an existing local account is exactly the takeover the design prevents. Plan for it
before enabling `SSO_ENFORCED_DOMAINS`, because that setting removes the password
and magic-link fallback those users still depend on.

### Find out which accounts need work

The administration panel has no user list, so use the read-only audit command.
It never writes and is safe against production:

```bash
python manage.py audit_user_identities --domain corp.com --provider google
```

```
EMAIL                  STATUS         PASSWORD  SIGN-IN RECORDS
adoptable@corp.com     adoptable      no        google
bound@corp.com         federated      no        google:https://accounts.google.com
passwordonly@corp.com  needs-import   yes       -

adoptable=1  federated=1  needs-import=1

1 account(s) would be refused after pinning this domain to 'google'. ...
```

| Status         | Meaning at cutover                                                    |
| -------------- | --------------------------------------------------------------------- |
| `federated`    | Already bound to the provider; nothing to do                          |
| `adoptable`    | Has a prior OAuth account for it; adopted on the next sign-in         |
| `needs-import` | Nothing links it to the provider; **refused** until its subject is imported |

`--provider` is what makes the distinction meaningful: an account bound to a
different provider still counts as `needs-import` when the domain is being pinned
to Google. Add `--csv` to produce a starting point for the import file, and
`--include-inactive` to see deactivated accounts, which are hidden by default.

Omit `--provider` for a general view of how everyone signs in today.

### Order of operations

Pin the domain **last**. Until that step, everyone keeps their existing sign-in
method, so a mistake is recoverable.

1. Configure Google and enable it, with `GOOGLE_AUTH_MODE=workspace` and the domain
   in `GOOGLE_WORKSPACE_DOMAINS`. Leave `SSO_ENFORCED_DOMAINS` empty for now.
2. Have each account in the `auto` group sign in with Google once. Confirm the user
   id and workspace memberships are unchanged.
3. For each account marked `NEEDS IMPORT`, collect its Google subject. In the Google
   Admin SDK this is the `id` field of `directory.users.get`; it is the same value
   Google puts in the `sub` claim. Build the CSV with an empty `subject_format`:

   ```csv
   user_id,email,subject,subject_format
   5e9158cd-7b35-46fb-a249-a27786bca342,person@corp.com,104729...,
   ```

4. Import with `--dry-run` first, review the report, then import for real:

   ```bash
   python manage.py import_federated_identities \
     --provider google \
     --issuer https://accounts.google.com \
     --file /secure/google-mapping.csv \
     --report /secure/google-mapping-report.json \
     --dry-run
   ```

   The issuer must be exactly `https://accounts.google.com`.
5. Have those accounts sign in with Google and confirm success.
6. Only now set `SSO_ENFORCED_DOMAINS=corp.com=google`. From this point the domain
   accepts Google alone; password and magic-link sign-in are refused for it.
7. Optionally set `SSO_AUTO_JOIN_WORKSPACES` so new colleagues land in a workspace
   instead of an empty account.

### Keeping administrative access

Pinning a domain removes password and magic-link sign-in for it, so decide in
advance how an administrator gets in if the identity provider is unavailable.

Two facts, both covered by tests:

- The policy governs only the domains it lists. An administrator whose address is
  outside them — a separate operations domain, not a personal mailbox — keeps
  password sign-in to the application. This is the recommended break-glass account,
  and it is also the account to use for merging or repairing users.
- The God Mode console at `/god-mode` authenticates against the password directly
  rather than through the provider adapters, so an instance administrator cannot
  lock themselves out of it by pinning their own domain. The corollary is that
  **pinning a domain does not protect the console**: its password is the only thing
  in front of it. Give it a strong, unique password and restrict who holds instance
  administrator rights.

### If someone is locked out afterwards

Their account still exists and nothing has been reassigned. Import the missing
subject as in step 3, or temporarily clear `SSO_ENFORCED_DOMAINS` to restore the
previous sign-in methods while sorting it out. Do not resolve it by deleting and
recreating the account: a new user id loses their memberships and history.

## Upgrade and migration procedure

### 1. Prepare recovery and evidence

1. Back up PostgreSQL and verify that the restore procedure works.
2. Confirm a local administrator can sign in without the provider being changed.
3. Export the authoritative provider-to-user mapping from the IdP. Record the
   exact issuer/entity ID, subject, SAML subject format, local user UUID, and email.
4. Disable the provider or schedule a maintenance window so identities cannot race
   the import.

The schema migration automatically backfills existing Google `Account` rows using
Google's canonical issuer. An existing OIDC account may be linked on first login
only when its legacy provider identifier matches the exact issuer/subject pair.
Existing SAML users require an authoritative mapping import. Prefer an explicit
import for every non-Google cohort during a controlled upgrade.

### 2. Apply migrations with SSO disabled

Deploy the application and run the normal migration job. Confirm the following
migrations complete:

- `db.0124_federated_sso_identity`; and
- `license.0008_secure_sso_configuration`.

Do not enable a provider if migration output reports a conflicting Google binding.
Investigate the duplicate ownership and restore from backup if the migration did
not complete atomically.

### 3. Build the import CSV

The file must be UTF-8 CSV with `subject`, `subject_format`, and at least one of
`user_id` or `email`. Supplying both local identifiers makes accidental matches
less likely.

```csv
user_id,email,subject,subject_format
5e9158cd-7b35-46fb-a249-a27786bca342,alex@example.com,00u123456789,
```

For SAML, use the exact configured representation:

```csv
user_id,email,subject,subject_format
5e9158cd-7b35-46fb-a249-a27786bca342,alex@example.com,employee-0042,attribute:employeeId
```

Keep the source file outside Git. It contains account-linkage data and may be
personal data under the operator's policy.

### 4. Validate and import

Run the command inside an API image with the same database configuration as the
deployment. Start with `--dry-run` and write the JSON report to a protected path:

```bash
python manage.py import_federated_identities \
  --provider oidc \
  --issuer https://idp.example.com \
  --file /secure/idp-mapping.csv \
  --report /secure/idp-mapping-report.json \
  --dry-run
```

Review every count and error. The command rejects duplicate subjects, missing
users, invalid rows, and bindings owned by another user. It makes no database
changes during a dry run.

Remove `--dry-run` only after review:

```bash
python manage.py import_federated_identities \
  --provider oidc \
  --issuer https://idp.example.com \
  --file /secure/idp-mapping.csv \
  --report /secure/idp-mapping-report.json
```

The import is atomic. It writes an append-only audit record containing the input
SHA-256 digest, source filename, row counts, and bounded report. It does not retain
the CSV itself.

### 5. Enable and verify

1. Enable only the migrated provider.
2. Sign in with a controlled existing user and confirm the original Hangar user ID,
   workspace memberships, and permissions are unchanged.
3. Change a test user's provider email, if supported, and confirm the same subject
   still reaches the same Hangar account.
4. Attempt a sign-in whose verified email belongs to a local user but whose subject
   is unbound; confirm it is rejected rather than linked.
5. For Google workspace mode, test one allowed and one disallowed hosted domain.
6. For SAML, replay a captured assertion in a test environment and confirm the
   second use is rejected.
7. Review authentication logs without collecting assertions, tokens, cookies, or
   client secrets.

Keep local recovery access until representative users have completed the flow.

## Failure handling and rollback

| Symptom                       | Meaning                                                                                  | Action                                                                                         |
| ----------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `SSO_ACCOUNT_LINK_REQUIRED`   | The asserted email belongs to an existing user, but the immutable identity is not linked | Disable the provider for that cohort and perform an authoritative CSV import                   |
| `FEDERATED_IDENTITY_CONFLICT` | The subject is already owned, identity fields changed, or a concurrent bind won          | Stop rollout; compare issuer, subject, and target user against the IdP export and import audit |
| `FEDERATED_IDENTITY_INVALID`  | Required identity fields or verified-email evidence are absent                           | Correct the IdP claims/configuration; do not bypass validation                                 |
| Google tenant rejected        | Workspace mode is active and the signed `hd` claim is not allowed                        | Correct the allowlist or the IdP tenant assignment                                             |
| SAML response rejected        | Signature, correlation, issuer, audience, timing, subject, or replay validation failed   | Inspect IdP/SP metadata and clocks; do not weaken validation                                   |

To stop a rollout, disable the affected provider and retain the identity rows. Do
not delete, edit, or reassign bindings to make a login succeed. Correct the IdP or
import mapping, test again, and then re-enable the provider.

Once federated identities have been used, do not reverse the schema migrations as
a normal rollback: doing so removes identity and import-audit data. Roll back the
application with the provider disabled only when the older code is compatible with
the migrated schema. Otherwise restore the pre-upgrade database backup and reconcile
any user or invitation changes made after that backup.

## Maintainer verification

The contract and unit suites cover Google token validation and tenant policy,
OIDC issuer/subject and verified-email behavior, SAML assertion validation and
replay protection, immutable/conflicting bindings, invitation lifecycle, import
validation, import idempotency, and transactional rollback. Run the repository's
documented API test workflow before release; do not substitute a provider smoke
test for those invariants.
