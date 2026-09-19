## Security and privacy

**Pasted HTML is now inspected in a document that cannot run it.**
When content was pasted into the editor, the paste handler assigned the clipboard's HTML
to a detached element's `innerHTML` in order to look for images worth uploading. A
detached element is not rendered, but it still fetches: `<img src=x onerror=…>` fires
while the markup is merely being examined, before anything decides whether to keep it.
The same shape was in the helper that extracts plain text from stored HTML. Both now
parse into an inert document, where nothing loads and nothing runs, and a test reads the
source of both helpers so the next person to reach for `innerHTML` here is stopped by a
failing build rather than by a reviewer's memory. This matches the fork's own markdown
paste handler, which already documented the hazard.

**Placing a workshop session requires the role that editing one requires.**
Editing a Workshop's sessions was already checked against the project role; scheduling
from the planner was not, and workspace membership alone was enough. A project guest —
someone deliberately given the narrowest seat — could therefore place sessions on a
Workshop and assign a trainer to them through the planner, while the ordinary work-item
route refused the same person. Both paths now ask the same question. The session-creating
paths also refuse an edit whose sessions collide, with each other or with another
workshop or a live reservation for the same trainer; that is a database question the
planner already asked, and editing a Workshop still does not contact Google.

**Reservations are bounded, and the paths that spend calendar quota are throttled.**
A reservation removes a trainer's time from circulation for seventy-two hours, and
nothing limited how many one person could hold, so one caller could take a roster out of
circulation with ordinary requests. Reservations and saved plans are now capped per
person per workspace. Taking or spending a reservation is throttled on the same budget
as the capacity ledger, deliberately shared: all three read Google before deciding
anything, so a caller who only ever receives conflicts still spends the quota the
ledger's throttle exists to protect. A deployment that leaves `ALLOWED_HOSTS` at its
wildcard default now says so in the log at startup.

**The background sweep reads calendar event titles. The availability path still does
not.** Reporting on training, and importing it as work items, both need to know what a
training was called, and the previous contract said no titles or descriptions were ever
requested. That is no longer true of the sweep, and the consent text on the capacity
page has been rewritten to say what is actually read. The OAuth scope is unchanged, so
existing authorizations remain valid — what changed is what is done with them, which is
why the copy changed rather than the permission.

The boundary is drawn deliberately narrowly. Titles are requested only through a
separate client method used by the sweep; the live availability path runs without them,
so no event summary reaches its cache or any of its responses. A title is kept only for
an event that already matched a rule on both organizer and attendee — the title of an
unrelated event in the same calendar is discarded in the same iteration that read it,
never stored and never logged. What is kept is truncated and encrypted with the same key
material as the rest of the calendar configuration, and is shown only to a workspace
administrator or to the trainer whose invitation it is. Everyone else sees the same
anonymous block as before.

## Migrations and compatibility

Upgrade from `0.1.0-rc.60`. This release introduces four additive migrations in the
fork's own application: `0030_workshop_checklist_templates`, `0031_workshop_roles`,
`0032_training_event_materialization` and `0033_training_import_marker`. They create
tables and backfill nothing. No existing table is altered, so the ordinary release Job
is sufficient and rollback is not constrained by schema state.

Product version is `v0.1.0-rc.61`, Git tag `hangar-v0.1.0-rc.61`, Helm chart version
`0.1.0-rc.61`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.0-rc.61`. No chart
resources, Secrets, storage, RBAC or NetworkPolicy contract changes are introduced.

**Materializing training is a second switch on top of calendar capacity, and is off.**
`ENABLE_GOOGLE_TRAINING_MATERIALIZATION=1` has no effect unless Google Calendar capacity
is enabled as well, so enabling the sweep can never accidentally enable capacity. With
it off, the new tables stay empty, the new periodic tasks return immediately, and the
product behaves exactly as it did in rc.60. The sweep's window and pacing are
configurable through `GOOGLE_TRAINING_SWEEP_WINDOW_PAST_DAYS` (90),
`GOOGLE_TRAINING_SWEEP_WINDOW_FUTURE_DAYS` (180), `GOOGLE_TRAINING_SWEEP_LEASE_SECONDS`,
`GOOGLE_TRAINING_SWEEP_BATCH` and `GOOGLE_TRAINING_RETIRED_RETENTION_DAYS`. Reservation
limits are `CAPACITY_MAX_ACTIVE_HOLDS_PER_USER` (ten) and
`CAPACITY_MAX_PLAN_DRAFTS_PER_USER` (fifty). Two periodic tasks are added to the
schedule: one dispatches calendar sweeps, one prunes retired occurrences overnight.

**A Workshop can start with the subtasks it always needs.** A workspace administrator
defines checklist templates in **Workspace settings → Workshop checklists**: an ordered
list of subtasks, each with a due date expressed as days before or after the workshop's
first session, and each optionally assigned. Assignment can name nobody, the workshop's
own trainer, a specific person, or a **role** — a standing job in running a workshop,
held by whoever currently does it. A role is the reason this is not just a list of
names: when the person who handles a recurring job changes, the role's membership
changes once and every future workshop follows, rather than every template being edited.
Applying a template creates real work items under the Workshop, so everything that works
on a work item works on them. Applying it twice adds only what is missing. A named
assignee who cannot hold work in the target project is reported rather than silently
dropped, and a role with nobody in it leaves its subtask unassigned rather than failing
the whole checklist.

**Training planned in the calendar can be reported on, and turned into work items.**
**Capacity → Training report** answers how much training a trainer ran over any period
up to four hundred days, reading the materialized record and the workshop sessions and
making no call to Google — which is the whole reason the record exists. It reports
Workshops, sessions, delivery and preparation minutes, and separately confirmed and
pending external training, and exports the same figures as CSV. Because the figures come
from a record rather than a live read, the response says how fresh it is, what window
has been collected, and whether the requested range falls inside it; a trainer whose
consent lapsed, or who has never been swept, is marked and excluded from totals rather
than reported as having run nothing.

**Team capacity → Import from calendar** lists recognized trainings that are not yet
linked to a session and creates a Workshop work item for the ones an administrator
selects, linking the invitation to the new session in the same transaction so the hours
are not counted twice. It is deliberately a review screen rather than an automatic
import: a calendar contains things that are not workshops, and undoing a mistake would
mean deleting work items.

**The team ledger can be narrowed to training, and names it.** The ledger takes a layer
filter — an **Only training** shortcut and per-layer toggles — kept in the URL alongside
the week, and recognized training carries its title for viewers entitled to it. Working
hours are always drawn, because they are the canvas the rest sits on.

Session edits that collide are now refused where they were previously accepted. A client
that submits overlapping sessions for the same trainer receives a conflict naming the
two sessions instead of a successful write. Consecutive sessions, the ordinary multi-day
case, are unaffected, and importing from the calendar deliberately skips this check,
since it records what the calendar already says is happening.

## Known limitations and rollback

**Hangar still does not write to the shared training calendar.** A workshop planned in
Hangar does not appear there, so it must still be entered by hand, and an invitation
entered that way is recognized as external training until somebody links it to the
session. The import screen closes this loop in the direction that matters today — pulling
existing calendar plans into Hangar — but the other direction is not in this release.
Until it is, the calendar is the source of truth and Hangar follows it.

Moving an invitation in Google changes the identity the fork derives for that occurrence,
so the moved event arrives as a new occurrence and the old one is retired at the next
full rescan. Any link between the old occurrence and a session is broken by that, and
the new occurrence must be linked again. This matches what the live path has always
done; it is now visible in the record as well.

Only the daily full rescan may conclude that an invitation disappeared. A quarter-hourly
pass asks Google for what changed since the last success, and an event moved outside the
collected window no longer matches the time filter, so an empty answer there means
"nothing changed" rather than "it is gone". Cancellations do not wait for the rescan.

A trainer who personally loses access to a rule's calendar keeps materialized rows until
a weekly access probe notices and marks them. Booking is unaffected, because the path
that admits a reservation still reads Google per trainer and fails closed for that
person; the exposure is confined to a report being generous for at most a week, and the
report marks a trainer it cannot vouch for.

A training rule accepts any calendar identifier, and nothing verifies that the workspace
is entitled to read it. The effective read scope is therefore the union of what the
consenting trainers can see. An operator should treat configuring a rule as an
administrative act with that reach, not as a display preference.

The collaborative editor gap described in rc.60 is unchanged by this release: content
persisted as a binary collaborative document is not inspected by the server-side HTML
allowlist. The paste fix above concerns what the browser does while examining clipboard
content, and does not close that gap.

Rollback to rc.60 restores the previous images. The four new tables remain and are
ignored by the older build, since nothing in it reads them; no schema state blocks the
downgrade. The new screens disappear, reservations become unbounded again, scheduling
from the planner stops asking for a project role and stops refusing colliding sessions,
and checklists already created remain as ordinary work items because that is all they
ever were. Materialized occurrences are left untouched and are picked up again if the
release is reapplied.

The evaluation qualification boundary remains AMD64. The production profile remains
unsupported; this release does not claim a new live-cluster qualification. Publication
verifies the chart and images through the release workflow. Deployment and acceptance on
the user's environment remain a separate step.
