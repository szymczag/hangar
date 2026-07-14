# Federated SSO security and migration

Status: operator security and migration guide for Google, OpenID Connect, and SAML 2.0.

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
