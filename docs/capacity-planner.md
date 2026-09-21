# Planning workshops

A plan stores requirements without reserving a trainer. You can search before
a Workshop work item exists. New plans default to a four-hour workshop with no
preparation or travel buffers; enter the buffers needed for the actual session.

Reserve a candidate for 72 hours when the time still needs agreement, or schedule
it directly. Scheduling requires an existing Workshop work item or one created
from the planner. Creating the work item does not book the trainer until the
session is confirmed. A failed confirmation retains the work item and any hold.

While a reservation is active, the plan name and its work item can change without
releasing the time. Changing its duration, buffers or eligible trainers requires
releasing the reservation. New plan and Saved plans preserve existing holds.
The saved-plan list distinguishes creation/update dates from session and expiry
dates.

Scheduling appends one session, assigns its trainer, and consumes the reservation
atomically. Repeated requests with the same idempotency key return the same session.
The key cannot be reused for a different request. No Google invitations are sent.

Booking checks fresh Google availability, working hours, existing workshops and
holds. A connected calendar that cannot be verified prevents new bookings.
Google can change after verification; Hangar does not lock external calendars.

The planner offers times only for trainers whose calendar it can read right now.
A trainer who has connected none returns no busy time at all, which is not a free
week but an unreadable one, so their booking hours are never offered as candidate
slots; the planner names them and says why instead. The same applies while a
connected calendar is stale, rate limited or unverifiable.

Booking enforces the same rule rather than trusting the client. A hold or a
direct schedule for a trainer with no connected calendar, or with a connection
but no calendars selected, is refused with `409 calendar_not_connected`: retrying
cannot help and only that trainer can resolve it. A connected calendar that
cannot be verified right now stays `503 availability_unverified`, which a retry
can clear.

Each trainer connects their own Google account, and availability is read with
that trainer's credential. Sharing a calendar with a coordinator in Google
therefore changes nothing here: Hangar never reads one person's calendar through
another person's connection, and nobody can connect on a colleague's behalf.

Migration ext.0027 adds nullable session origins and booking-operation records.
Existing plans and sessions remain valid. Old clients retain the hold/schedule
API; new clients can PATCH title/issue_id during a hold and schedule a candidate
directly using an idempotency key. Apply migrations before deploying the new API.

## Workshop checklists

A workspace administrator defines checklist templates in **Settings → Workshop checklists**.
Each template is a named, ordered list of subtasks; a workspace may keep up to twenty
templates of up to thirty items each. One template may be marked as the default.

Each item carries a title, an optional description, an assignment rule and a day offset.
The assignment rule is one of: nobody, a specific person, the workshop's own trainer, or
whoever holds a **workshop role**. The trainer rule resolves when the template is applied,
against the Workshop's active trainer assignees, so one template serves every trainer. A
person who is not an active project member able to hold work is skipped rather than
assigned, and the response names them.

**Workshop roles** are defined in the same screen: a role is a standing job in running a
workshop — streaming, feedback, materials — and the people who currently do it. A template
names the role, so when the rota changes an administrator edits the role once instead of
every template that mentioned the departing person. A role holds up to 25 people and a
workspace up to 30 roles; only workspace administrators change them.

Applying an item in role mode assigns everyone who currently holds that role, so
responsibility is visible and the holders settle it between themselves. A role nobody holds
yet leaves the subtask unassigned rather than failing — an empty rota is a staffing
question, not a reason to refuse the whole checklist. Deleting a role releases every
checklist item that named it back to unassigned; the items themselves are never deleted.

Applying a template creates the subtasks under the Workshop work item, each as an ordinary
child work item with its own history entry. Application is idempotent by subtask name:
applying the same template twice adds nothing, and applying it again after the template
gained an item adds only that item. Only Workshop work items accept a checklist.

The day offset is counted from the workshop's first session, negative for before it. A
Workshop exists before it has a date, so subtasks created at that point have no due date;
scheduling the workshop fills them in, counting calendar days in the trainer's timezone so
that offsets spanning a daylight-saving change land on the day people expect. A due date
already set by hand is never overwritten. Editing or deleting a template leaves the
subtasks it has already created untouched.

The planner applies the default template to a Workshop it creates. That call is best
effort: a workspace with no default template, or an unavailable checklist endpoint, does
not prevent the workshop from being created.

Migrations `ext.0030` and `ext.0031` add the template, item, origin and role tables and
their audit actions. Existing workshops are unaffected; a workspace with no templates
behaves exactly as before.

## Timezones and workload

Booking hours follow the connected primary Google calendar's IANA timezone. Without
that connection they follow the trainer's Hangar profile. The last successfully
read Google timezone remains in use during provider outages; disconnecting returns
to the profile timezone. Calendar metadata refreshes at most once per day during an
uncached availability read. Existing weekly hours retain their local clock values;
the previous capacity-specific timezone override no longer applies.

The viewer's profile timezone determines week boundaries, displayed candidate dates,
and morning/afternoon filters. Weeks and days spanning daylight-saving transitions
use calendar boundaries rather than fixed 24-hour arithmetic.

Team workload counts distinct Workshop items and sessions with delivery overlapping
the selected week. Delivery and preparation/travel minutes are clipped to that
period and summed per assignment, including work outside booking hours. Concurrent
assignments therefore remain visible as separate commitments. Active, unexpired
reservations are separate from scheduled delivery. Aggregate workload exposes no
restricted work-item names. The existing occupancy metrics remain available for
backwards compatibility and continue to measure overlapping booking hours.

Migration `0028_calendar_primary_timezone` adds nullable refresh metadata and an
initially empty Google timezone. Existing connections populate it on their next
uncached calendar read.

## Recognizing training invitations

Workspace administrators configure **Team capacity → Training calendar rules**.
A rule names one calendar, and every event on it counts as a training. Calendar
identifiers are encrypted using the existing calendar encryption key; only
workspace administrators can read or change rules. No organization-specific
identifiers belong in repository files.

Whose training it is comes from the trainer's own copy of the invitation, not
from the shared calendar's guest list -- a shared calendar normally hides that,
and Google hides it from the API too. The full mechanism, the measurements behind
it and the design that it replaced are in
[training recognition](capacity-training-recognition.md); that document is the
reference for this subsystem.

Each trainer then opens **My capacity → Allow training calendar access**. This
separate consent adds `https://www.googleapis.com/auth/calendar.events.readonly` to
the existing read-only connection. Configure that optional scope on the Google OAuth
consent screen before using this feature. Existing connections keep their original
permissions until the trainer opts in. An administrator's rule grants no Google
permissions, and nobody can grant this consent on a trainer's behalf: a trainer
who has not granted it is reported as such rather than as having run no training.
Disconnecting Google removes the connection and indexed caches.

Accepted invitations count as confirmed external training; tentative and
unanswered invitations count separately as pending. Both block booking. Declined
and cancelled invitations are ignored. Recurring instances are expanded and are
distinguished from one another, and all-day end dates are exclusive in the source
calendar timezone.
Two reads with different field masks serve this. The rule's calendar is asked
for times and titles, which is safe because every event on it is a training. The
trainer's own calendar is asked for times and their own response only -- no title
and no description of a private meeting is ever requested from it, which is a
stronger guarantee than discarding one. No attendee list or organizer address
appears in any response.

Successful reads are cached for five minutes. Last-known results can be displayed
for up to one hour with an unverified status. New holds and scheduling always require
a fresh read of all configured sources. Missing consent, inaccessible calendars and
provider errors therefore block new bookings until resolved; they are never treated
as free time. Remove an obsolete rule in Team capacity when that source no longer
applies to this workspace.

**Your recognized training invitations** in Team capacity lets a trainer explicitly
link an invitation to an overlapping Workshop session they deliver and can access.
The linked invitation continues to block time but no longer adds external delivery
minutes. Unlinking restores its external workload. No fuzzy title matching or automatic
Workshop creation is performed. If a linked session no longer assigns that trainer
or no longer overlaps the period, the invitation counts again. No Google events or
invitations are created or modified.

Migration `0029_google_training_rules` adds encrypted identity/configuration fields,
per-connection opt-in, and explicit invitation/session links. Deploy the API and
apply migrations before enabling rules in the frontend. Existing workspaces without
rules retain free/busy-only behavior.

Session updates accept each existing session's `id` and preserve that row, its plan
origin and invitation links, including when sessions are reordered. IDs must be
unique and belong to the edited Workshop. Removing a session removes its links;
legacy clients that omit IDs retain the replace-all behavior.

Editing a Workshop's sessions requires the same project role as editing the work
item itself, and scheduling from the planner now requires it too: workspace
membership alone was enough before, so a project guest could place sessions and
assign a trainer through the planner while the work-item route refused them.

Session edits are refused when they collide. Submitted sessions are checked
against each other and against other workshops and live reservations for the
same trainer; the Workshop's own stored sessions are ignored, since they are
being replaced. This is the database question the planner already asks, not a
Google read -- editing a Workshop has never contacted Google and does not start
now. Google availability remains the planner's concern, at the point where time
is actually taken. Consecutive sessions, the ordinary multi-day case, are
unaffected.

Importing a training from the calendar deliberately does not perform this check:
it records what the calendar already says is happening, so refusing an overlap
there would refuse to reflect reality.

Reservations and saved plans are capped per person per workspace
(`CAPACITY_MAX_ACTIVE_HOLDS_PER_USER`, default ten; `CAPACITY_MAX_PLAN_DRAFTS_PER_USER`,
default fifty). A reservation removes a trainer's time from circulation for
seventy-two hours, so the number one person may hold at once is a direct limit
on everybody else's ability to book, and nothing bounded it before. Expired
reservations hold nothing and do not count.

Taking or spending a reservation is throttled with the same limits as the
capacity ledger, and shares its budget on purpose: both read Google before
deciding anything, so a caller who only ever receives conflicts still spends the
quota the ledger's throttle exists to protect.

## Materializing recognized training

The ledger reads Google on every request, which is right for a week and
impossible for a quarter: Google will not serve a roster's month in one request,
and an event listing refuses a window holding more than two thousand events. A
background sweep therefore records what it recognizes, and reporting reads only
that record.

Enable it with `ENABLE_GOOGLE_TRAINING_MATERIALIZATION=1`, which has no effect
unless Google Calendar capacity is enabled as well. The sweep covers a rolling
window — ninety days back and one hundred and eighty forward by default,
configurable — snapped outwards to whole months so its boundary does not shift
daily. The window is how far back the sweep re-reads, not how much history is
kept: older occurrences are left alone, because a report about last year is what
the record exists to answer.

Sweeping is keyed on the rule's calendar rather than on each trainer. A rule
names a shared calendar, so every consenting trainer would read an identical
event list from it; one read per calendar is fanned out in memory against each
consenting trainer's own verified address. Consent is unchanged by this: an
occurrence is still only recorded for a trainer who has granted the training
scope themselves.

A pass every quarter hour asks Google only for what changed since the last
success, with a short overlap so an event updated mid-pass is not missed. Such a
pass may never conclude that an invitation disappeared: an event moved outside
the window no longer matches the time filter, so an empty answer means "nothing
changed", not "everything is gone". A full rescan runs daily and is the only
pass permitted to retire an occurrence by absence. Cancellations do not wait for
it — a cancelled invitation is matched by its own occurrence key and retired
immediately, because a cancelled training that goes on blocking a trainer is
what somebody plans staffing around.

Calendars are handed to workers by lease, so two dispatchers divide the work
rather than sweeping the same calendar twice. A lease that expires is
reclaimable, which is what makes a worker dying mid-sweep self-healing. A Google
failure is recorded on the calendar's own row and backs off there; it never
discards what was already known, because stale rows with an honest freshness
marker beat an empty table. Retired occurrences are deleted after a grace
period; nothing else is ever pruned.

Event titles are requested on this path only, through a separate client method.
The live availability path keeps running without them, so no event summary
reaches its cache or any of its responses. A title is kept only for an event
that already matched a rule — organizer and attendee both — and is stored
encrypted with the same key material as the rest of the calendar configuration.

## Importing calendar training as Workshops

Training planned in the calendar blocks time and counts in the report, but it is
not a work item, so nothing can be attached to it: no checklist, no status, no
client contact. **Team capacity → Import from calendar** lists recognized
trainings that have no linked session, and creates a Workshop work item for the
ones an administrator selects.

A training is listed once however many trainers it has, and importing it creates
one work item, its schedule and one session with **every** trainer on it,
assigns them all, and links each trainer's invitation to that session in one
transaction. Selecting any trainer's row imports the whole training: importing
half of it would leave the other half to become a second Workshop later.

A trainer who cannot hold work in the chosen project is left out and stays
listed. Once they join the project, importing that row again puts them on the
Workshop that already exists rather than creating another. The link
is what stops the training being counted as delivery and as external training at
the same time. "Not yet imported" means the invitation has no link — never a
work item with a similar name; no title matching is performed.

The calendar title becomes the work item's name. Without one, the rule's label
and the date are used. A trainer who is not an assignable member of the chosen
project is reported rather than imported unassigned, and one such row does not
stop the rest of the batch. Importing is administrator-only, and still requires
a seat in the target project.

## Filtering the team ledger

Team capacity draws several kinds of commitment at once, and the question being
asked is usually about one of them. **Only training** narrows the timeline to
booking hours and recognized training in a click; the individual toggles are
there because "why is this person unavailable" is usually answered by a
different layer. Working hours are always drawn, since they are the canvas the
rest sits on. The selection lives in `?layers=`, so a narrowed ledger can be
pasted into a message like any other link.

Where a training's title has been recorded, the timeline names it. The title
comes from the sweep's record rather than from a live read -- the availability
path still never asks Google for event summaries, so none reach its cache -- and
is shown only to a workspace administrator or to the trainer looking at their
own week. Everybody else, and any window the sweep has not yet reached, sees the
generic label.

## Training report

**Capacity → Reports** answers how much training a trainer ran over any period
up to four hundred days. It reads the materialized record and the workshop
sessions, and makes no call to Google — which is the whole reason the record
exists.

Per trainer it reports distinct Workshops, sessions, delivery minutes and
preparation/travel minutes, and separately confirmed and pending external
training. An invitation linked to a session counts as delivery only, exactly as
in the weekly ledger. `export=csv` returns the same figures as a download.

Because the figures come from a record rather than a live read, the response
says how fresh it is: when each calendar was last swept successfully and last
fully rescanned, what window has been collected, and whether the requested range
falls inside it. A trainer whose consent lapsed, or who has never been swept,
is marked and excluded from totals rather than reported as having run nothing.

Migration `0032_training_event_materialization` adds the occurrence record and
the sweep bookkeeping. It is additive and backfills nothing; a workspace that
never enables materialization behaves exactly as before.
