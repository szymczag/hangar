# Second factor for the God Mode console

The instance-admin console at `/god-mode` holds authority over the whole
instance. It is deliberately **not** covered by `SSO_ENFORCED_DOMAINS`: it checks
the password directly rather than going through the provider adapters, which is
what stops an administrator locking themselves out by pinning their own domain.
The consequence is that its password used to be the only control in front of it.

A WebAuthn security key is now required in addition to that password, for every
instance administrator.

## What changes for administrators

Signing in becomes two steps. The password step no longer creates a session — it
records who proved a password and sends the browser to the second factor. An
administrator with no key registered is sent to enrollment instead and cannot
open the console until they register one.

**Deploying this signs every administrator out.** Existing sessions carry no
second-factor marker, so they stop being accepted. That is intended.

## Requirements

WebAuthn is a browser API with two hard constraints that are not ours to relax:

- **The console must be served over HTTPS**, except on `localhost`. An instance
  reachable only over plain `http://` at a real hostname cannot use security keys
  at all.
- **The relying-party ID must match the console's origin.** See below.

Before enabling this on an existing instance, sign in once immediately after
deploying, while you still have a shell open.

## Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `WEBAUTHN_RP_ID` | derived | Relying-party ID. Derived from `ADMIN_BASE_URL`, else `WEB_URL` |
| `WEBAUTHN_RP_NAME` | `Hangar` | Name shown by the authenticator |
| `WEBAUTHN_ALLOWED_ORIGINS` | derived | Comma-separated exact origins an assertion may come from |
| `ADMIN_WEBAUTHN_REQUIRED` | `1` | Set to `0` only to recover a locked-out instance |
| `ADMIN_2FA_PENDING_ASSERT_WINDOW` | `300` | Seconds a password-verified sign-in may wait for its key |
| `ADMIN_2FA_PENDING_ENROLL_WINDOW` | `900` | The same, for enrollment |
| `ADMIN_2FA_CHALLENGE_TTL` | `300` | Seconds a challenge stays valid |
| `ADMIN_2FA_MAX_ATTEMPTS` | `5` | Failures before the pending state is discarded |

### Getting the relying-party ID right

This is the one setting that can lock everyone out, so it is worth a minute.

The RP ID is checked by the **browser**, against the origin of the page that
calls `navigator.credentials` — the admin panel, not the API. It must be the
panel's host, or a parent domain of it. Anything else fails inside the browser
with a `SecurityError`, before a request reaches Hangar.

| Deployment | Panel origin | Correct `WEBAUTHN_RP_ID` |
| --- | --- | --- |
| Panel under the app (default) | `https://hangar.example.com` | derived — leave unset |
| Local development | `http://localhost:3001` | derived — leave unset |
| **Panel on its own subdomain** | `https://admin.example.com` while the app is `https://app.example.com` | **`example.com`** — set it explicitly |

In the third case the derived value would be `admin.example.com`, which stops
working the moment the app origin is also allowed. Use the shared parent. That
is safe because the *server* still pins the acceptable origins exactly, so an
assertion obtained by another subdomain fails verification here.

Hangar refuses to issue options for a configuration the browser would reject and
returns `ADMIN_2FA_NOT_CONFIGURED` naming the values that disagree, rather than
letting it fail silently in the console.

## Recovery

There are no recovery codes. A lost key is reset from a shell:

```bash
python manage.py disable_instance_admin_2fa --email admin@example.com --list
python manage.py disable_instance_admin_2fa --email admin@example.com
```

`--list` is read-only. The reset removes that administrator's credentials and,
unless `--keep-sessions` is passed, their live console sessions — if the key was
lost together with the laptop, leaving the thief's session alive would defeat
the point. They enroll a new key at the next sign-in.

The command works when the message broker is down, which is deliberate: recovery
must not depend on a healthy instance.

**Register a second key.** With CLI-only recovery, one key means one hardware
failure away from needing server access.

## What is enforced

| Property | How |
| --- | --- |
| A password alone opens nothing | The password step never creates a session; `request.user` stays anonymous |
| A half-authenticated session grants nothing | `InstanceAdminPermission` additionally requires a completion marker |
| A challenge is used once | Conditional `UPDATE`, not read-then-write, so concurrent verifies cannot both win |
| A challenge belongs to one session | Bound to the issuing session key |
| Registration cannot authenticate | Challenges carry a purpose |
| A cloned authenticator is caught | Signature-counter regression disables the credential |
| A key cannot be claimed twice | `credential_id` is unique instance-wide, at the database level |
| Guessing is bounded | Dedicated throttles plus a per-session attempt cap |

Every cryptographic failure answers the same error code, so the response cannot
distinguish an unknown credential from a bad signature.

Signature counters are only checked when the authenticator uses them — many
report zero forever, and treating that as a clone would lock those devices out.
The check is ours rather than the library's, because py_webauthn only rejects a
regressed counter; disabling the credential needs the distinction between a bad
signature and a cloned key.

Registration and assertion are covered end to end by a software authenticator
(`plane/tests/support/webauthn_device.py`) that produces real ES256 signatures,
so the verification path is exercised rather than assumed. What that cannot
cover is the browser itself: whether a given deployment's relying-party ID
satisfies Chrome is a property of the browser and of DNS, so **test one real
sign-in with a real key before enabling this on an instance you care about**.

## Scope

This is a **second factor**, not a passkey: credentials are registered
non-resident with preferred user verification, and the password remains
required. Passwordless sign-in would change the recovery story and is a separate
decision.
