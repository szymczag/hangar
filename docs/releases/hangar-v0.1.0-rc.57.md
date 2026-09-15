## Security and privacy

**Activity notifications are no longer discarded in silence.**
rc.56 made the notification template render again, which exposed the fault behind it:
the mailer took the application's own base URL from a per-issue cache key with a ten
minute expiry, and returned early when it was missing — before writing an outbox row,
before marking the notification processed, and before any of the attempt bookkeeping.
The row stayed pending, was re-selected every five minutes forever, and produced no
log line, no exception and no counter. The dependency was never real: that value comes
from the instance's own configuration and never varied per request, so it is now read
directly and the cache is gone. One consequence is worth stating on its own: the cache
key could only be written by a request-handling process, so notifications raised by
scheduled automation — closing and archiving stale work items — could never be
delivered at all.

**A notification that cannot be built now gives up and says why.**
Failures that no retry can clear are recorded and stopped rather than repeated
indefinitely. A work item or recipient that no longer exists ends the attempt at once,
an instance with no configured base URL is counted like any other failure and reaches a
terminal state, and the reason is kept on the row. Previously each of these left a
notification that looked pending forever.

**A trainer whose calendar cannot be read is no longer offered or booked.**
A trainer with no connected Google calendar returns no busy intervals, which the
planner read as an empty week rather than as an unreadable one. Candidates were built
from booking hours alone and the booking preflight accepted the hold, so the one
trainer nobody could see was the one who could always be booked — and the booking is
the irreversible half. A single rule now gates candidate generation, the availability
arithmetic, the per-trainer search and the alert, and the server refuses an unreadable
calendar with a conflict rather than a retryable error, because no retry can clear it.
The empty state now names the missing calendar instead of blaming booking hours, which
had been sending coordinators to the wrong setting. Hangar reads each trainer's
calendar with that trainer's own credential; sharing a calendar with a coordinator in
Google does not reach Hangar, and nobody can connect one on a colleague's behalf.

**Encrypted notifications can describe themselves in the Subject, if an operator asks.**
The outer subject of an encrypted message is the one header encryption cannot cover. It
stays the generic `Encrypted Hangar notification` unless an administrator enables
descriptive subjects in God Mode under Email delivery, which makes an activity
notification read `INFRA-3 updates: Broken login flow - new comment from Ada L` instead.
That reveals the work item reference, its title and the first commenter to the mail
provider, its logs and its backups, and to anyone who can see the mailbox list. The
protected subject, body, comments, receipt and attachments stay inside the encrypted
entity either way. The setting is off unless it is turned on, so upgrading discloses
nothing new.

## Migrations and compatibility

Upgrade from `0.1.0-rc.56` with a database backup and apply the release migration Job
before admitting traffic to the new API and web images. Two migrations are introduced
and both are additive. `db.0133` records the outer subject as sent on each outbox row,
so the integrity check before delivery has something to verify against now that the
subject is no longer a constant. `license.0023` adds the setting that controls
descriptive subjects, seeded off.

Product version is `v0.1.0-rc.57`, Git tag `hangar-v0.1.0-rc.57`, Helm chart version
`0.1.0-rc.57`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.0-rc.57`. No chart
resources, Secrets, storage, RBAC or NetworkPolicy contract changes are introduced.

Every activity notification held back by the cache-key fault is sent on the first
scheduled run after the upgrade. These were never expired, only unrenderable, so they
are delivered normally rather than discarded — but a workspace that has been quietly
accumulating them since before rc.56 receives the whole backlog at once, describing
changes that may be several days old. Nothing is lost and nothing is duplicated.

Deployments that pin trainer bookings to Google Calendar should expect fewer offered
candidates immediately after the upgrade: a trainer who has not connected a calendar is
now excluded rather than offered with a warning label. That is the point of the change,
but it is visible as a reduction in availability rather than as an error.

## Known limitations and rollback

Descriptive subjects are all or nothing. There is no per-project or per-recipient
control, and a work item title that carries customer or incident detail carries it into
the Subject header for every recipient of that notification. Leave the setting off
unless the titles in an instance are safe to disclose to the mail provider.

A notification that reached its attempt ceiling is not retried after the cause is fixed.
The row is terminal and its reason is recorded; the underlying activity remains visible
in Hangar. Only notifications that were still pending are delivered by this upgrade.

Enabling OpenPGP still holds project notifications, exports and known-user invitations
for every account without a verified key. Account access and recovery mail is never
encrypted and never held.

Rollback to rc.56 restores the previous images and returns the mailer to taking the base
URL from the cache, which reintroduces the silent loss this release removes. Reversing
the two migrations discards the recorded outer subjects and the descriptive-subject
setting; an instance that had enabled it must enable it again after rolling forward.
Encrypted messages already queued keep their stored subject, so reverse the migrations
only after the outbox has drained.

The evaluation qualification boundary remains AMD64. The production profile remains
unsupported; this release does not claim a new live-cluster qualification. Publication
verifies the chart and images through the release workflow. Deployment and acceptance on
the user's environment remain a separate step.
