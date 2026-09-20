## Security and privacy

**Rich text stored through the API is sanitized against one allowlist, wherever
it came from.** Descriptions, comments, pages and stickies are stored as HTML the
editor writes, but the API accepts that HTML from any client. Every write path
now runs it through `validate_html_content`, built on nh3 — the Rust `ammonia`
sanitizer, the server-side counterpart of DOMPurify. Script, style, iframe, form
and every `on*` handler are removed; URL attributes accept `http`, `https`,
`mailto` and `tel` only.

nh3 does not look inside attribute values, and some values become styling or a
request path in whatever renders the HTML, so values are checked as well: colour
attributes take palette keys, identifiers must be UUIDs — another name can
clobber a global in the page that renders it — classes are restricted to those
the editor owns, and image sources to an asset identifier or an http(s) URL.

**The frontends now send an enforced Content-Security-Policy.** Web, admin and
space sent one report-only before; `contentSecurityPolicy.reportOnly` defaults to
`false` and the policy is enforced, with violations still reported to the API and
logged there. Enforcing is backed by what runs under it: every screen of the
visual suite, and the security suite's sign-in through the real forms, the editor
and its pastes, comments, stickies, pages through Live, PDF export, published
boards, screenshot uploads, and a deliberately refused foreign image.

Two rules decide whether a deployment needs anything more. **Images are this
instance's own** — the chart adds the object-storage origin itself, an image a
description points at on another host is not loaded, and a profile picture from
an identity provider is copied into object storage at sign-in. **Sign-in posts to
the API, which answers with a redirect**, and Chrome checks `form-action` on that
redirect, so the public origin and base URLs must be the origins users actually
open or the form is refused and sign-in silently does nothing.

Trusted Types keep a switch of their own and stay in `report`: the policies are
installed and observe every DOM sink that still takes a plain string, without
deciding anything yet.

**Training recognition no longer depends on a guest list that shared calendars
hide.** Recognizing a trainer's invitation required finding them in the
attendees of an event on the rule's calendar. A shared organizational calendar is
normally configured to hide its guest list, and Google honours that in the API —
measured on a real calendar over two months, 188 events carried one guest list
between them. Recognition therefore matched almost nothing and reported it as a
trainer who had run no training, with no error anywhere to say otherwise.

A rule is now the calendar alone. What a training is and what it is called comes
from that calendar; whose it is, and how they answered, comes from the trainer's
own copy of the invitation, matched on the occurrence identity. **The privacy
boundary narrows rather than widening**: the trainer's own calendar is read under
a field mask that requests no titles and no descriptions, so the titles of their
private meetings are never sent rather than merely discarded, and trainers no
longer need permission to see the details of the shared calendar at all. The
OAuth scope is unchanged.

**Writing into the shared calendar is a separate consent, with a separate scope.**
The coordinator who keeps the training calendar connects their own Google account
per rule — no service account — and that connection asks for `calendar.events`
plus identity and none of the reading scopes, because a coordinator who connects
only to create entries has no use for free/busy or the calendar list. The writing
account is checked again before every write: a rule whose writer changed under a
queued entry blocks rather than letting somebody else's account act on a consent
that was not theirs.

The fixes to pasted HTML, reservation limits and scheduling authorization
described in `0.1.0-rc.61` carry forward unchanged.

## Migrations and compatibility

Upgrade from `0.1.0-rc.61`. This release introduces four migrations. Three in the
fork's own application — `0034_training_rule_organizer_optional`,
`0035_training_rule_writer_credential` and `0036_workshop_calendar_outbox` —
create tables and columns and backfill nothing. One in the license application,
`0024_remove_unsplash_access_key`, drops a stored key that is no longer read. The
ordinary release Job is sufficient.

Product version is `v0.1.0-rc.62`, Git tag `hangar-v0.1.0-rc.62`, Helm chart
version `0.1.0-rc.62`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.62`.

**An operator has three things to check before upgrading.** First, the origins:
`hangar.publicOrigin` and the base URLs must be the origins users actually open,
or the enforced policy refuses the sign-in form and sign-in does nothing visible.
Second, images stored before this release that point at another host — run
`python manage.py localize_external_images` in an API pod, which reports first
and applies with `--apply`. Third, storage served from a further origin of yours
belongs in `contentSecurityPolicy.imgSrc`; nothing else does, because the chart
adds the object-storage origin itself. Setting
`contentSecurityPolicy.reportOnly: true` watches violations without blocking
anything, which is the way to add an origin.

**Training materialization is now reachable from the Helm chart.** It shipped in
`rc.61` as an environment variable the chart never rendered, and the chart has no
free-form environment, so a Helm deployment could not enable the training report
or the calendar import at all. `googleCalendarCapacity.materialization` now
carries the switch and the sweep window, bounded to the same ranges the
application enforces so an impossible value is refused by `helm template` rather
than by a container that then refuses to start.

**Writing workshops into the shared calendar is off by default**, behind
`ENABLE_GOOGLE_CALENDAR_WRITEBACK` on top of calendar capacity — the only part of
this subsystem that changes somebody else's calendar rather than reading it.
With it on, scheduling a workshop records what the calendar ought to say inside
the booking's own transaction and a worker sends it afterwards, so a slow or
unreachable Google cannot make a booking fail. The event identifier is derived
from the session and the trainer, so a redelivered message cannot produce a
second invitation. The event covers the delivery window rather than the
preparation and travel around it. Only the trainer is invited.

A Workshop's session list reports each invitation per trainer, with a retry that
clears the backoff when something is stuck; a training rule reports whether its
writing account is connected, needs reconnecting, or never granted permission to
create events.

The trainer consent text said Hangar would never create events or send
invitations. With write-back enabled it does both, through a separate account,
never touching the trainer's own calendar — the text now says so.

## Known limitations and rollback

**Recognition depends on trainers holding their own copy of each invitation.**
A training entered on the shared calendar without inviting the trainer is not
recognized as theirs, because nothing else establishes whose it is. This is the
ordinary way such a calendar is used, but it is a requirement rather than an
assumption the software can work around.

**A trainer who has not granted training recognition is reported as such**, not
as somebody who ran no training, and nobody can grant it on their behalf. That
distinction is now visible in My capacity, in the team ledger and in the report;
before this release the two were indistinguishable, which is how a workspace can
spend an evening believing it has no trainings rather than no consent.

**Write-back depends on one person's token staying healthy.** That was the
explicit trade against a service account: the trail Google keeps names somebody
who can be asked about an entry. A rule with no writer, or one whose token
expired, parks its entries rather than failing anybody's booking, and one retry
clears the backlog once the account is reconnected.

Moving an invitation in Google changes the identity derived for that occurrence,
so the moved event arrives as a new one and the old is retired at the next full
rescan. Any link between the old occurrence and a session breaks with it. This is
unchanged from `rc.61` and is now visible in the record as well as on the live
path.

Trusted Types are installed and observing, not enforcing. An operator reading
this release should treat the DOM-sink inventory as measurement rather than a
control, and the collaborative editor gap described in `rc.61` is unchanged:
content persisted as a binary collaborative document is not inspected by the
server-side allowlist. The sanitization above concerns what the API stores.

Rollback to `rc.61` restores the previous images. The three new tables and
columns remain and are ignored by the older build; the dropped license key is not
restored by a downgrade and must be re-entered if that build is expected to use
it. The enforced policy reverts to report-only, the calendar write-back surfaces
disappear, and any workshop already written to the shared calendar stays there —
Hangar stops maintaining it rather than removing it, so an operator downgrading
with write-back enabled should expect entries the older build will not update.

The evaluation qualification boundary remains AMD64. The production profile
remains unsupported; this release does not claim a new live-cluster
qualification. Publication verifies the chart and images through the release
workflow. Deployment and acceptance on the user's environment remain a separate
step.
