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
Each rule matches both a calendar ID and the exact organizer email. The event
creator does not affect matching. Calendar IDs and organizer emails are encrypted
using the existing calendar encryption key; only workspace administrators can read
or change rules. No organization-specific identifiers belong in repository files.

Each trainer then opens **My capacity → Allow training calendar access**. This
separate consent adds `https://www.googleapis.com/auth/calendar.events.readonly` to
the existing read-only connection. Configure that optional scope on the Google OAuth
consent screen before using this feature. Existing connections keep their original
permissions until the trainer opts in. The trainer's Google account must itself be
able to read the configured shared calendar; an administrator's rule grants no
Google permissions. Disconnecting Google removes the connection and indexed caches.

Hangar matches the trainer through the verified Google account email, not the
calendar copy's `self` flag. Accepted invitations count as confirmed external
training; tentative and unanswered invitations count separately as pending. Both
block booking. Declined and cancelled invitations are ignored. Recurring instances
are expanded, and all-day end dates are exclusive in the source calendar timezone.
The importer requests times, organizer and participant responses; it requests no
titles or descriptions and exposes no attendee lists or organizer addresses in the
team workload response.

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
