## Security and privacy

**Work item notifications are sent at all, for the first time.**
The template behind them could not be parsed, so rendering raised on every run of
the stacking task -- every five minutes, for days -- and the row was never marked
processed, so it was picked up and failed again forever. Three conditionals had been
reflowed across newlines, which Django's lexer stops recognising as tags, and two of
them split a quoted state name mid-literal so it could never have matched even once
rejoined. In-app notifications were built on a different path and were unaffected,
which is why nothing surfaced it. A failing render now gives up after a few attempts
and records why, instead of retrying in silence, and the whole template tree is
parsed by the test suite so this cannot return unnoticed.

**Encrypted notification email is delivered instead of being held indefinitely.**
Mail delivery runs on its own Celery queue so a deployment can give the mail worker a
narrowly scoped cloud identity and give the general worker none. Only the Helm chart
ever ran the worker that consumes that queue; every Compose deployment inherited the
routing without a consumer. An encrypted notification was therefore rendered, encrypted
and stored, then published to a queue nobody read, and the outbox row stayed at `queued`
indefinitely. Nothing reported a fault, because publishing had succeeded and no consumer
existed to fail. The due-row dispatcher that exists to recover exactly this runs on the
same queue and was stranded with it. Clear account mail takes a different path and is
submitted inline by its producer, so sign-in codes, password resets and the console test
message kept working throughout — which made a successful test message read as proof
that notification delivery worked. All three Compose files now run a mail worker.

**Invitations are confined to the domains an instance actually signs in with.**
Pinned sign-in domains were enforced at sign-in and nowhere near an invitation, so
an administrator on an OIDC-only instance could invite an address that could never
accept: the row was written, the mail was sent, and the refusal arrived only when the
invitee tried to sign in -- by which point an outsider had been told the workspace
name and the inviter's address. All three paths that write an invitation now refuse
up front. Confining invitations to the pinned domains is off by default and is
enabled in God Mode under Authentication, beside the domains it depends on. Two
refusals apply regardless: a plus tag on a directory-backed domain, because those
directories issue no account carrying a tag, and a domain pinned to no provider at
all, because nobody there can sign in. The invite field now refuses an uninvitable
address as it is typed rather than after submitting.

**Project invitations can be created again.**
Every call to the project invite endpoint failed. The workspace-role guard read a role
off a queryset rather than off a member, and the send loop called a Celery method on a
local list instead of the task, so either path raised an error before an invitation was
written and the endpoint answered 500 to every caller. The role is now read as a column,
an address with no workspace role is allowed through the guard rather than crashing it,
a role arriving as a JSON string is compared as a number, and an unparseable one is
refused with 400. The guard's own rejection previously carried no status and so returned
200 with an error body; it now returns 400.

**Notification settings say when an unverified key is silencing email.**
Once an instance enables OpenPGP, project notifications for an account with no verified
key are suppressed rather than sent in the clear. That is the intended protection, but it
happened invisibly: the notification preferences offered the same switches either way and
every one of them was inert. The page now states that email is being held and names the
missing step — no key enrolled, a key uploaded but never verified, or an address the
provider suppressed after a bounce or complaint — and links the first two to the place
that fixes it. The preferences are still saved and begin producing email as soon as a key
is verified.

**The community deployment can reach its own mail settings.**
The environment list in the community Compose file is the entire environment its API
containers receive, and it carried no `EMAIL_*` variable at all. `EMAIL_DELIVERY_V2_ENABLED`
set in `variables.env` never reached a container, so durable delivery — and therefore
OpenPGP — was unreachable on that deployment whatever else was configured. The mail
settings an operator owns are now forwarded, and documented where an operator looks.

**The trainer calendar picker shows calendar identifiers.**
Training calendar rules match on a calendar's identifier, but the picker listed only
its display name, so the only way to read the value a rule needs was Google Calendar's
own settings. The identifier is now shown under the name.

## Migrations and compatibility

Upgrade from `0.1.0-rc.55` with a database backup and apply the release migration Job
before admitting traffic to the new API and web images. Two migrations are introduced
and both are additive. `db.0132` adds an attempt counter and last-error field to the
email notification log, so a notification that cannot be built stops being retried
forever and says why. `license.0022` adds the instance setting that confines
invitations to the pinned sign-in domains, seeded from
`RESTRICT_INVITES_TO_SSO_DOMAINS` and off unless an operator turns it on.

Neither migration rewrites or removes existing rows, so a rollback drops the two
columns and the one setting and nothing that existed before this release.

Product version is `v0.1.0-rc.56`, Git tag `hangar-v0.1.0-rc.56`, Helm chart version
`0.1.0-rc.56`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.0-rc.56`. The chart's
contract is unchanged: it already ran a dedicated mail worker, and no Secret, storage,
RBAC or NetworkPolicy contract is affected.

Compose deployments gain a `mail-worker` service. Installations that take
`docker-compose.yml` from the release assets receive it automatically; an operator who
maintains a modified copy must add the service, which is the ordinary API image with
`HANGAR_WORKER_QUEUE=email`. Without it, encrypted notification email continues to
accumulate unsent. Community deployments should review the new `EMAIL_*` and `SMTP_*`
entries in `variables.env`; all of them default to the previous behaviour, so an
installation that does not set them is unchanged by this release.

Encrypted notifications that accumulated at `queued` under an earlier version are
delivered once a mail worker consumes the queue. They are not re-encrypted and their
original content and recipient are preserved.

## Known limitations and rollback

Every activity notification that accumulated while the template was broken is sent on
the first scheduled run after the upgrade. They carry no expiry, so a workspace that
has been quietly collecting them receives the whole backlog at once, describing
changes that may be several days old. Nothing is lost and nothing is duplicated; it
simply arrives together.

Queued messages that carry a validity window do not survive the backlog. The encrypted
key test is enqueued with a one-hour window, so a test message stranded by a missing
mail worker is recorded as permanently failed with an expiry reason the first time a
worker leases it, rather than being delivered late. Repeat the test after the worker is
running. Project notifications carry no expiry and are unaffected.

Enabling OpenPGP still holds project notifications, exports and known-user invitations
for every account without a verified key, and this release makes that visible rather
than changing it. Enable encryption only once the people who expect notification email
have enrolled a key. Account access and recovery mail is never encrypted and never held.

A mail worker consumes the queue but does not diagnose a rejecting SMTP server; a
message refused by the provider is recorded with its typed failure in the delivery
ledger and is not retried past its attempt ceiling.

Rollback to rc.55 restores the previous images and, on Compose, removes the mail worker
along with them, which returns encrypted notification email to accumulating unsent, and
restores the unparsable template, which stops activity notifications again. No data is
lost by doing so and the outbox rows remain. Reversing the two migrations removes the
notification attempt counters and the invitation restriction setting; an instance that
had enabled the restriction must re-enable it after rolling forward again.

The evaluation qualification boundary remains AMD64. The production profile remains
unsupported; this release does not claim a new live-cluster qualification. Publication
verifies the chart and images through the release workflow. Deployment and acceptance on
the user's environment remain a separate step.
