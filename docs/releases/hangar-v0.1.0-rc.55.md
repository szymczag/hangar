## Security and privacy

**Planning now supports both temporary reservations and direct scheduling.**
Explore trainer availability without a work item, then choose an existing Workshop
or create one at confirmation. A held plan can acquire its Workshop without
releasing the reservation. Confirmation records the originating plan, consumes a
hold atomically, and uses an idempotency key to prevent duplicate sessions on retry.
The API rechecks the complete block against booking hours, internal commitments
and fresh Google availability. Concurrent reservations cannot claim the same time.

**Saved plans and booking hours are easier to manage.**
The planner separates saved-plan selection, saving and starting a new plan. Searchable
saved plans show creation/update dates and reservation or session dates. Switching
with unsaved changes offers save, discard or cancel. New plans start with zero
preparation and travel buffers, and explain the full continuous block required.
The hours editor keeps focus while typing, validates on blur/save, aligns days and
copies all intervals to active days or all seven days. Pro labels are removed.

**Capacity uses automatic timezones and shows trainer workload.**
Booking hours follow the primary Google calendar timezone, with the Hangar profile
as fallback. A temporary provider failure retains the last known Google timezone.
The viewer's profile determines displayed weeks, dates and morning/afternoon
filters, including daylight-saving transitions. Team capacity separates Workshop
counts, session counts, delivery, preparation/travel and provisional reservations.

**Private calendar rules recognize training invitations.**
Workspace administrators configure encrypted calendar and organizer rules in Team
capacity. Each trainer explicitly grants additional read-only event access through
their own Google account. Accepted invitations contribute external training effort;
pending invitations are separate and both block bookings. Declined/cancelled events
are ignored. Titles and descriptions are not requested, and attendee lists are not
exposed to the team. No Google events or invitations are written.

**Explicit links prevent duplicate training workload.**
Trainers can link recognized invitations to overlapping Workshop sessions they
can access and deliver. Linked invitations continue to block time without adding
a second delivery total. Unlinking restores external workload. Matching never
creates Workshop items automatically or guesses from titles.

## Migrations and compatibility

Upgrade from `0.1.0-rc.54` with a database backup and apply the release migration Job
before admitting traffic to the new API and web images. Migrations `ext.0027` through
`ext.0029` add booking operation records and session origins, primary-calendar
timezone metadata, encrypted Google identities and training rules, per-connection
training consent, and explicit invitation/session links. Existing sessions, plans
and weekly clock-hour values are retained. The old capacity-specific timezone
override no longer controls booking hours.

Product version is `v0.1.0-rc.55`, Git tag `hangar-v0.1.0-rc.55`, Helm chart version
`0.1.0-rc.55`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.0-rc.55`.
No chart resources, Secrets, storage, RBAC or NetworkPolicy contract changes are
introduced. Existing capacity enablement and encryption-key settings remain valid.

For invitation recognition, add `calendar.events.readonly` to the Google OAuth
consent configuration. Trainers then grant this optional scope in My capacity and
must have access to the configured shared calendar. Rules are entered in the app;
do not place organization-specific calendar IDs or organizer addresses in Git.
See [planner setup](../capacity-planner.md) and the
[configuration reference](../kubernetes/configuration.md#google-calendar-trainer-capacity).

## Known limitations and rollback

Connected calendar failures, missing required training consent or inaccessible
configured calendars block new holds and scheduling. Last-known results may be
shown for one hour but cannot authorize a booking. Availability checks cannot make
an external Google calendar transaction atomic with Hangar; a later external edit
can still create a conflict. No Google write-back is performed.

Workshops still require one continuous opening including all buffers. Search stays
bounded to eight fourteen-day windows and responses to 25 trainers. Workspace
training rules apply to all trainers; remove rules for sources that no longer
apply. External training has no automatic Workshop item creation. Explicit links
are managed by the trainer delivering the session.

Rollback images to rc.54 only after considering the loss of the new booking checks
and invitation-based blocking. Prefer retaining the additive database schema.
Reversing the migrations removes operation history, origin links, timezone metadata,
training rules, consent flags and invitation links; it does not remove Workshop
sessions. Back up those records before a schema rollback. Restore prior settings
manually if returning to capacity-specific timezone overrides.

The evaluation qualification boundary remains AMD64. The production profile remains
unsupported; this release does not claim a new live-cluster qualification. Publication
verifies the chart and images through the release workflow. Deployment and acceptance
on the user's environment remain a separate step.
