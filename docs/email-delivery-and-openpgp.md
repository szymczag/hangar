# Email delivery and OpenPGP

Status: implemented architecture and security model.

Last reviewed: 2026-07-14.

This document explains why Hangar uses Amazon SES, what OpenPGP does and does not protect, which messages are deliberately unencrypted, and how users can verify a suspicious message. Operators should continue with [Amazon SES email operations](aws-ses-email-operations.md). Maintainers should use [Email delivery technical reference](email-technical-implementation-plan.md).

Examples use reserved domains and placeholder AWS values. Deployment-specific identifiers and credentials belong in the deployment secret system, never in this repository.

## Decision

Hangar uses the Amazon SES v2 API in `eu-central-1` for transactional delivery. The application submits raw MIME over authenticated HTTPS with a workload identity. It does not need a paid Google Workspace mailbox, an SMTP password, a stable source IP, or an IP allowlist.

Use a dedicated transactional subdomain, for example:

| Purpose                    | Example                             |
| -------------------------- | ----------------------------------- |
| Human and Workspace mail   | `example.com`                       |
| Hangar visible From domain | `hangar.example.com`                |
| Visible sender             | `Hangar <hello@hangar.example.com>` |
| SES custom MAIL FROM       | `bounce.hangar.example.com`         |
| DMARC record               | `_dmarc.hangar.example.com`         |

This separates application reputation and DNS authorization from normal human mail. The custom MAIL FROM host is an SES routing domain; it is not an inbox and must not receive Google Workspace MX records.

Running a small local Postfix/OpenDKIM relay is technically possible but does not remove the difficult work: IP reputation, reverse DNS, queue recovery, bounce and complaint processing, abuse response, blocklist monitoring, provider throttling, and delivery to large mailbox providers. A local relay in front of SES also adds another privileged queue without improving the selected trust boundary.

## Provider alternatives

The application retains provider-neutral SMTP transports, but the production deployment and feedback pipeline are optimized for SES API delivery.

| Provider              | Strength                                                                                                         | Trade-off                                                                            | Fit                         |
| --------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | --------------------------- |
| Amazon SES, Frankfurt | Mature raw MIME, DKIM, custom MAIL FROM, suppression, configuration-set events, workload identity, usage pricing | US-headquartered processor; controller must complete its DPA and transfer assessment | Selected default            |
| Scaleway TEM, Paris   | EU provider, transactional focus, SMTP, DKIM and webhooks                                                        | Smaller ecosystem; raw PGP/MIME and event semantics require a deployment proof       | Strong sovereignty fallback |
| EmailLabs, Poland/EEA | Regional support and deliverability expertise                                                                    | Commercial plan and detailed log-retention/privacy model need review                 | Strong managed fallback     |
| Mailjet or Brevo      | Familiar European transactional products and simple onboarding                                                   | Broader marketing/contact and tracking surface                                       | Viable, less narrow         |
| Self-hosted MTA       | Full software control                                                                                            | Operational and reputation burden; often still needs a smarthost                     | Not recommended initially   |

Selecting an EU AWS region is not, by itself, a complete GDPR decision. The controller still owns the provider contract, transfer mechanism and assessment, retention, access controls, transparency, lawful basis, incident process, and current subprocessor review. This documentation is technical guidance, not legal advice.

## Threat and trust model

SPF, DKIM, DMARC, transport TLS, receipts, and OpenPGP have different jobs:

| Control        | Property                                                                       |
| -------------- | ------------------------------------------------------------------------------ |
| SPF            | Authorizes SES for the SMTP envelope domain                                    |
| DKIM           | Authenticates selected headers and message bytes for the sending domain        |
| DMARC          | Requires identifier alignment and publishes receiver policy                    |
| HTTPS/SMTP TLS | Protects a transport hop                                                       |
| OpenPGP        | Encrypts the selected MIME payload to the user's public key                    |
| Hangar receipt | Lets the signed-in user confirm that this Hangar instance recorded the message |

OpenPGP delivery is server-side encryption, not end-to-end encryption against Hangar. Hangar already processes the project data and renders plaintext before encryption. A compromised application, worker, template, or authorized operator could therefore access or alter content before it is encrypted.

For encrypted mail, SES and the recipient mailbox can still observe the sender, recipient, timestamp, Message-ID, message size, routing data, and generic outer subject. The protected subject, message body, attachments, and receipt are inside PGP/MIME.

DKIM authenticates the transmitted message and domain, but the user's mailbox UI may hide the details. The in-product receipt gives the user a separate authenticated channel. Neither mechanism proves that every link in a message is safe; users should still navigate to Hangar directly for sensitive actions.

## Email policy

Hangar has one central policy. Individual tasks cannot decide to fall back to cleartext.

### Unencrypted account mail

The following stay minimal and unencrypted even when a public key exists:

- magic sign-in and password reset;
- email verification and email change codes;
- account activation or deactivation;
- OpenPGP key activation, replacement, and removal alerts; and
- an invitation to an address that does not yet map to a Hangar user.

These messages are needed to access or recover the account. Encrypting them to a missing, expired, or lost key could permanently lock out the user or hide a key-change warning from the legitimate owner.

Every permitted cleartext account message starts with this meaning in both text and HTML:

> Security notice: This message is unencrypted because it is required to access or secure your Hangar account. To receive project and activity notifications by email, add and verify an OpenPGP public key in Profile → Security. Until then, those notifications remain available only in Hangar.

Cleartext subjects and bodies must not include project names, work-item titles, comments, exports, webhook details, or other confidential content.

### Encrypted or held notifications

Known-user invitations, project/activity notifications, exports, and operational details require a verified, unexpired public key. With a usable key, Hangar sends standards-compliant PGP/MIME. Without one, it creates a payload-free receipt and keeps the underlying notification in Hangar; it does not send a reduced cleartext copy.

A hard bounce, complaint, or active notification preference can also suppress sending. The profile page explains active address suppression, and an instance administrator can remove it only after reviewing and recording a reason.

## OpenPGP message format

Hangar uses PGP/MIME (`multipart/encrypted` as defined by RFC 3156), not inline armored text. The outer subject is always:

```text
Encrypted Hangar notification
```

The real subject, text/HTML alternatives, receipt, and attachments are encrypted together. Remote images, trackers, embedded objects, forms, scripts, and CSS network loads are removed before the message is stored.

Each user receives a separate message encrypted to the exact encryption key version selected at enqueue time. Hangar never groups recipients with different keys and never accepts or stores a private key.

## User key lifecycle

The Email security section in Profile → Security supports:

1. uploading one ASCII-armored public certificate;
2. reviewing the complete primary and selected encryption-key fingerprints;
3. receiving and decrypting an expiring challenge through the real mail path;
4. entering the challenge to activate the key;
5. sending a compatibility test; and
6. replacing or removing the key after recent authentication.

Upload alone is not enough. The encrypted challenge proves control of the corresponding private key. The existing active key remains active until a replacement completes verification.

Hangar rejects private-key material, malformed or oversized certificates, expired/revoked/disabled keys, signing-only certificates, weak RSA encryption keys, excessive certificate structure, and unsupported algorithms. Certificate processing is isolated and cannot retrieve keys from a network.

The user's private key remains solely in their mail client or key-management environment. It must not be pasted into Hangar, sent to support, or stored in a browser profile field.

## Client expectations

Thunderbird has native OpenPGP support and is the reference desktop workflow. Import the private key into Thunderbird, confirm that its full fingerprint matches the key shown in Hangar, and decrypt the challenge and test messages there.

For a command-line workflow, save the complete raw message and let a PGP/MIME-aware client or tool extract the `encrypted.asc` MIME part before running GnuPG. Do not copy only a rendered snippet from webmail; MIME boundaries and transfer encoding matter.

Google Workspace/Gmail webmail does not provide a universal native PGP/MIME workflow. A deployment that expects Gmail-browser users must standardize and security-review a client, extension, gateway, or local workflow before enabling encrypted notification email for those users. Hangar should not weaken the format or upload private keys to solve a client limitation.

## Verifying a suspicious email

Every message generated by the secure outbox contains a code such as:

```text
Hangar email receipt: 4A7C-91D2-0F35-A18B-CC40
```

To verify it:

1. Do not follow a link in the suspicious message.
2. Open the known Hangar URL directly and sign in.
3. Open Profile → Security → Email receipts.
4. Enter the complete receipt code.
5. Compare the sender snapshot, generic mail type, encryption mode, creation time, and delivery status.

No result means the current account and Hangar instance have no matching record; treat the email as suspicious. A result means Hangar recorded a message of that type for this user. It does not certify arbitrary message body text, so a mismatched time/type or a copied old receipt is still suspicious.

Administrators can search the instance delivery ledger by exact receipt or recipient, see provider correlation and typed failures, and review active suppressions. Neither ledger stores or displays the message body.

## Privacy boundaries

Hangar stores queued message bodies only in an application-encrypted outbox and purges them after delivery, permanent failure, or the short operational retention window. The longer-lived audit receipt contains routing metadata and status, not message content.

SES tags contain only an opaque outbox UUID and a low-cardinality policy class. Outer encrypted subjects are generic. Open/click tracking and message archiving must remain disabled. Raw SNS/SQS events must not be copied to logs; Hangar persists only bounded delivery metadata.

Public certificates are not secrets, but they are personal security data and remain encrypted at rest in the application database. Access is limited to the owner-facing lifecycle and the mail worker that needs a selected certificate.

## Failure behavior

- A missed Celery publication is recovered from the database by the due-row dispatcher.
- A temporary provider error is retried with a bounded lease and backoff.
- A response lost after SES submission becomes `acceptance_unknown` and is not blindly resent.
- A provider event can reconcile accepted, delivered, bounced, complained, rejected, delayed, or rendering-failure state.
- An older provider event cannot regress a newer state.
- A hard bounce or complaint activates local suppression immediately.
- A missing, revoked, or expired key never causes a cleartext fallback.
- An unsupported payload version or corrupt encrypted row fails closed and purges no unrelated data.

## Remaining deployment responsibilities

The code cannot provision or approve external controls. Before production, the operator must:

- complete the AWS contractual and privacy review;
- verify the dedicated sending identity, DKIM, custom MAIL FROM, SPF, and DMARC;
- configure configuration-set events, SNS, SQS, a dead-letter queue, alarms, and least-privilege workload identity;
- request production access and establish an intentional warm-up volume;
- test raw PGP/MIME with supported clients and controlled recipient providers;
- define a monitored Reply-To address, abuse/security contacts, and suppression recovery process; and
- monitor reputation, queue health, delivery failures, key expiry, and DNS continuously.
