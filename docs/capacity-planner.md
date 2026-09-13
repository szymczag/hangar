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
Without a connected calendar, only Hangar availability can be checked.
Google can change after verification; Hangar does not lock external calendars.

Migration ext.0027 adds nullable session origins and booking-operation records.
Existing plans and sessions remain valid. Old clients retain the hold/schedule
API; new clients can PATCH title/issue_id during a hold and schedule a candidate
directly using an idempotency key. Apply migrations before deploying the new API.

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
