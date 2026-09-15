## Security and privacy

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

**The community deployment can reach its own mail settings.**
The environment list in the community Compose file is the entire environment its API
containers receive, and it carried no `EMAIL_*` variable at all. `EMAIL_DELIVERY_V2_ENABLED`
set in `variables.env` never reached a container, so durable delivery — and therefore
OpenPGP — was unreachable on that deployment whatever else was configured. The mail
settings an operator owns are now forwarded, and documented where an operator looks.

**Notification settings say when an unverified key is silencing email.**
Once an instance enables OpenPGP, project notifications for an account with no verified
key are suppressed rather than sent in the clear. That is the intended protection, but it
happened invisibly: the notification preferences offered the same switches either way and
every one of them was inert. The page now states that email is being held and names the
missing step — no key enrolled, a key uploaded but never verified, or an address the
provider suppressed after a bounce or complaint — and links the first two to the place
that fixes it. The preferences are still saved and begin producing email as soon as a key
is verified.

**Project invitations can be created again.**
Every call to the project invite endpoint failed. The workspace-role guard read a role
off a queryset rather than off a member, and the send loop called a Celery method on a
local list instead of the task, so either path raised an error before an invitation was
written and the endpoint answered 500 to every caller. The role is now read as a column,
an address with no workspace role is allowed through the guard rather than crashing it,
a role arriving as a JSON string is compared as a number, and an unparseable one is
refused with 400. The guard's own rejection previously carried no status and so returned
200 with an error body; it now returns 400.

## Migrations and compatibility

Upgrade from `0.1.0-rc.55`. This release introduces no database migrations and no
schema change, so no migration Job is required beyond the ordinary release Job and
rollback is not constrained by schema state.

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
along with them, which returns encrypted notification email to accumulating unsent. No
data is lost by doing so and the outbox rows remain. Because no migration is introduced,
a rollback has no schema consequence.

The evaluation qualification boundary remains AMD64. The production profile remains
unsupported; this release does not claim a new live-cluster qualification. Publication
verifies the chart and images through the release workflow. Deployment and acceptance on
the user's environment remain a separate step.
