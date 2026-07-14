# Email delivery technical reference

Status: implemented.

Last reviewed: 2026-07-14.

This document is the maintainer reference for Hangar's outbound email subsystem. For deployment steps and day-two operations, use [Amazon SES email operations](aws-ses-email-operations.md). For the security model and user-facing behavior, use [Email delivery and OpenPGP](email-delivery-and-openpgp.md).

All examples use reserved domains and placeholder AWS identifiers. Never add a production domain, address, account number, ARN, queue URL, or credential to this repository.

## Architecture

```text
producer task or API action
        │
        ▼
template registry + central policy
        │
        ├── clear account mail
        ├── PGP/MIME notification
        └── suppressed receipt, with no payload
        │
        ▼
encrypted EmailOutbox row ──► dedicated Celery mail queue
        ▲                              │
        │ minute dispatcher            ▼
        └──────────────────── SES v2 SendEmail (raw MIME over HTTPS)
                                       │
                              SES configuration-set event
                                       │
                                       ▼
                              SNS ──► SQS ──► mail worker
                                                   │
                                                   ▼
                                      state, receipt, suppression
```

The selected production transport is `ses_api`. It uses the SES v2 `SendEmail` operation with raw MIME so RFC 3156 PGP/MIME and attachments remain under application control. Configuration sets and opaque message tags are API parameters, not MIME headers. `ses_smtp` remains a compatibility transport; generic `smtp` never receives SES-specific headers.

## Code map

| Area | Location |
| --- | --- |
| Public enqueue API and rendering | `apps/api/plane/mailer/service.py` |
| Policy classes and decisions | `apps/api/plane/mailer/policy.py`, `enums.py` |
| Allowlisted templates | `apps/api/plane/mailer/registry.py` |
| Stored-payload encryption and receipt codes | `apps/api/plane/mailer/crypto.py` |
| Clear and PGP/MIME construction | `apps/api/plane/mailer/mime.py` |
| Constrained GnuPG adapter | `apps/api/plane/mailer/openpgp.py` |
| SES API and SMTP transports | `apps/api/plane/mailer/transports/` |
| Delivery, recovery, feedback, retention | `apps/api/plane/bgtasks/email_delivery_task.py` |
| Durable models | `apps/api/plane/db/models/email.py` |
| User key and receipt API | `apps/api/plane/app/views/user/email_security.py` |
| Admin log and suppression API | `apps/api/plane/license/api/views/email_delivery.py` |
| User UI | `apps/web/core/components/settings/profile/content/pages/` |
| Admin UI | `apps/admin/app/(all)/(dashboard)/email/` |
| Kubernetes deployment | `charts/hangar/` |

## Policy invariants

Every producer supplies an allowlisted `template_key`. The registry fixes the policy class, configuration-set class, receipt label, and cleartext security-notice behavior. A producer cannot ask for an insecure fallback.

| Policy class | No verified key | Verified, unexpired key |
| --- | --- | --- |
| Account access | Minimal cleartext | Minimal cleartext |
| Account security | Minimal cleartext | Minimal cleartext |
| Invitation to an unknown address | Minimal cleartext | Not applicable |
| Invitation to a known user | Suppressed | PGP/MIME |
| Project/activity notification | Suppressed | PGP/MIME |
| Export | Suppressed | PGP/MIME |
| Operational detail | Suppressed | PGP/MIME |

Suppression is a successful policy outcome, not a delivery failure. The outbox stores a payload-free audit receipt and the source in-app notification is retained.

The account-access path intentionally stays cleartext because a magic link, password reset, email change, or key-recovery flow cannot depend on a key that may be missing or lost. Such messages contain the standard security notice and must not contain project information.

## `EmailOutbox` contract

An outbox row is both a delivery state machine and a privacy-minimized receipt. Important invariants are:

- `idempotency_key` uniquely identifies the domain intent;
- `intent_digest` prevents one idempotency key from aliasing different recipient, template, or content data;
- recipient and queued payload are encrypted with versioned authenticated encryption;
- recipient lookup and intent hashes use a separate keyed HMAC;
- the sender, policy, template label, configuration set, delivery mode, Message-ID, and receipt code are immutable snapshots;
- the receipt code is an 80-bit keyed value derived from the outbox UUID and is scoped to the user in the API;
- suppressed rows never contain a message payload;
- a delivered or permanently failed row has no message payload; and
- unsupported `payload_schema_version` values fail closed.

The body is never copied into the audit API. An administrator can see recipient routing data and typed errors, while a user can see only their own receipt metadata.

### State model

```text
queued ──► processing ──► accepted ──► delivered
  ▲            │              │
  │            ├──► failed_retryable
  │            ├──► acceptance_unknown
  │            └──► failed_permanent
  │
  └──── minute due-row dispatcher

policy/provider terminal states:
suppressed_no_key | suppressed_bounce | suppressed_complaint |
suppressed_preference | failed_permanent | delivered
```

Only `queued`, `failed_retryable`, and an expired `processing` lease can be leased. Delivery attempts are bounded and back off with jitter. A read timeout after SES submission becomes `acceptance_unknown`; Hangar does not blindly retry because SES may already have accepted the message. A subsequent SES event can reconcile that state.

The producer uses an on-commit Celery publication. RabbitMQ publisher confirms and bounded publish retries surface an initial publication failure. Independently, the minute dispatcher republishes due database rows, so a committed outbox row is not lost when a broker publication is missed.

## SES feedback trust boundary

The consumer accepts only the configured SNS topic and AWS sending account, a bounded allowlist of SES event types, a valid opaque `outbox_id` tag, and an event whose provider Message-ID does not conflict with an already recorded SES receipt. Raw event bodies are not logged or retained.

Events are deduplicated by a stable digest. State updates occur under a row lock. An older event cannot regress state established by a newer event. Hard bounces and complaints create an active local suppression, purge the queued payload, and terminate delivery. A new terminal event reactivates a suppression that an operator had previously removed.

Invalid SQS messages are left in the queue for the redrive policy and dead-letter queue. The consumer drains bounded batches for at most 45 seconds per scheduled run.

## OpenPGP lifecycle

Hangar accepts only an ASCII-armored public certificate. Private-key blocks are rejected. GnuPG runs without a shell, configuration files, autostart, key retrieval, or keyserver discovery, in a fresh mode-0700 home with a minimal environment and a ten-second timeout.

Parsing permits one primary certificate and bounded counts of identities, subkeys, and signatures. The selected encryption-capable key must be RSA 3072 bits or stronger, or a supported ECDH key of at least 255 bits. Selection prefers a valid encryption subkey, then the newest valid key, then the later expiry. Effective expiry is the earlier of primary-key and encryption-key expiry.

The lifecycle is:

1. The user recently authenticates and uploads a public certificate.
2. Hangar invalidates any previous pending replacement and stores a new pending version.
3. Hangar sends a random, expiring challenge through the real encrypted delivery path.
4. Verification is serialized under database locks, uses a keyed digest and constant-time comparison, and permits five attempts.
5. The previous active key becomes `replaced` only after the pending key is verified.
6. Removal requires recent authentication, revokes the record, and consumes outstanding challenges.
7. Activation and removal produce minimal cleartext security alerts.

There can be only one active and one pending, non-deleted key per user. In-flight messages retain the exact key version selected when they were queued; a replaced key remains usable for those rows, while revoked or expired keys fail closed.

## MIME and content handling

Encrypted mail uses `multipart/encrypted; protocol="application/pgp-encrypted"`. The outer subject is always `Encrypted Hangar notification`; the real subject, text/HTML alternatives, receipt, and attachments are inside the encrypted MIME entity.

HTML is sanitized before storage. Remote images, embedded objects, scripts, forms, SVG, remote stylesheets, event handlers, dangerous URL schemes, and CSS network loads are removed. Subjects, reply addresses, sender configuration, attachment names, MIME types, counts, and total sizes are validated before persistence. Each recipient receives an independent message.

The receipt is appended to both text and HTML. In encrypted mail it is inside the encrypted entity. A receipt proves that the current Hangar instance recorded an email intent for this user; it is not a cryptographic signature over arbitrary content and does not replace DKIM or OpenPGP.

When `EMAIL_DELIVERY_V2_ENABLED=0`, producers retain the pre-migration behavior: they validate and send directly through the configured transport without touching the secure outbox or requiring its cryptographic keys. This compatibility mode has no durable retries, OpenPGP, or receipt ledger. Enabling durable delivery is therefore an explicit, coordinated deployment change; do not enable the flag without the mail worker, database migrations, crypto secrets, and feedback infrastructure.

## API authorization

All `/api/users/me/email-security/` endpoints use the authenticated user from the session and never accept a user identifier. Receipt queries are limited to the user's foreign-key rows or the keyed hash of their current email. Exact receipt search is supported, but global receipt enumeration is not.

Instance email-log and suppression endpoints use the existing instance-administrator permission. Suppression removal requires an exact suppression ID and a recorded operator reason of at least ten characters. The row is locked during review to prevent concurrent operators from overwriting the decision.

## Retention

- queued payloads remain only while delivery is actionable;
- delivered, suppressed, and permanently failed payloads are purged immediately;
- accepted and acceptance-unknown payloads are purged after `EMAIL_OUTBOX_RETENTION_DAYS`;
- privacy-minimized receipts remain through `EMAIL_AUDIT_RETENTION_DAYS`;
- minimized provider events remain through `EMAIL_EVENT_RETENTION_DAYS`; and
- expired challenges are removed after their short cleanup grace period.

Rotate outbox encryption keys by prepending a new `version:base64url-key` entry and retaining old entries until every encrypted row using them has expired. Do not casually rotate the lookup HMAC key: receipt codes, address lookup, idempotency intent hashes, and local suppression correlation depend on it. A lookup-key rotation requires an explicit data migration and coexistence plan.

## Adding a template

1. Register a unique template key and non-sensitive audit label in `registry.py`.
2. Select the most restrictive applicable policy class.
3. Render both text and sanitized HTML without remote resources.
4. Choose an event-derived idempotency key; never use a constant for a recurring action.
5. Identify a `recipient_user` whenever the address belongs to an existing user. The service rejects mismatches.
6. Give expiring authentication messages an `expires_in` shorter than the underlying token lifetime.
7. Add policy, suppression, MIME, receipt, and producer tests.
8. Confirm no direct SMTP or SES call exists outside the transport package.

## Verification commands

```bash
podman compose -f docker-compose-test.yml run --rm api-tests \
  pytest plane/tests/unit/mailer plane/tests/unit/license/test_email_configuration_secrets.py -q

helm lint charts/hangar

./node_modules/.bin/oxlint \
  apps/admin/app/\(all\)/\(dashboard\)/email \
  apps/web/core/components/settings/profile/content/pages/email-security.tsx \
  apps/web/core/components/settings/profile/content/pages/email-receipts.tsx
```

Run the full repository checks before merging. Production validation additionally requires the SES mailbox simulator, real controlled recipients, raw-source inspection, and the supported OpenPGP client matrix.
