## Security and privacy

`rc.8` replaces email-based federated-login matching with immutable provider,
issuer, and subject bindings. OIDC and SAML login state is bound to a short-lived,
single-use correlation cookie, workspace invitations expire and are consumed
atomically, and existing deployments must explicitly migrate non-Google identity
bindings before those users can sign in.

Secure transactional email is disabled by default and uses a dedicated worker
when enabled. It adds least-privilege Amazon SES delivery, feedback and suppression
handling, auditable delivery receipts, bounded retention, and optional verified
OpenPGP encryption. Account-access messages are never retained as recoverable
plaintext by the outbox.

The new Todoist importer is restricted to workspace administrators. It validates
bounded CSV input before creating data, requires explicit assignee and module
decisions, sanitizes imported rich text, stores source files in a separate private
bucket, rejects anonymously readable uploads, and removes sources after completion
or within 24 hours. The Hangar Runner release surface is limited to an installation
consent and audit control plane; it does not execute untrusted workflows in this
release.

## Migrations and compatibility

This release applies Django database migrations `db.0122` through `db.0124`,
`license.0008`, and `ext.0004` through `ext.0006`. They create the secure-email,
federated-identity, Runner-control, and import-job records; backfill Google identity
bindings and invitation expiry; and harden Runner consent and audit evidence. The
Runner hardening migration deliberately fails if legacy audit or installation data
cannot be converted without losing required actor or consent evidence.

Before upgrading, take coordinated PostgreSQL and object-storage backups. Run the
Helm upgrade with `--wait-for-jobs` and do not admit application traffic from the
new revision until the migration Job succeeds. Existing OIDC and SAML users require
the documented reviewed identity-binding import before login; email similarity is
not accepted as proof of identity. Enabling secure email additionally requires the
documented SES, SQS, DNS, IAM, Secret, retention, and worker configuration. Enabling
Todoist imports require a distinct private import bucket; the application startup
creates and verifies it for the bundled object-storage profile.

The qualified Kubernetes boundary remains Kubernetes 1.30 through 1.36, including
1.36.2, Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a NetworkPolicy-enforcing CNI, and persistent storage. Production
support remains unavailable.

## Known limitations and rollback

Runner execution, workflow checkout, secret injection, artifact handling, and
runner-to-control-plane communication are not implemented. Secure email supports
Amazon SES only and requires operator-provisioned cloud and DNS resources. Todoist
imports accept UTF-8 CSV files up to 5 MiB and 10,000 rows; recurring schedules,
times, time zones, and durations are preserved as metadata rather than native
scheduling rules. Imports are additive and cancellation or rollback does not delete
already-created project data.

Do not roll application images back to `rc.7` against a database migrated by
`rc.8`. The new schemas and identity semantics are not qualified for mixed-version
operation, reverse migrations do not restore deleted or transformed evidence, and
Helm rollback does not remove imported work items or restore external email and
object-storage state. To return to `rc.7`, restore the coordinated pre-upgrade
PostgreSQL and object-storage backups into a clean environment and deploy the
`0.1.0-rc.7` chart. Prefer correcting configuration or migration data and completing
the forward upgrade.
