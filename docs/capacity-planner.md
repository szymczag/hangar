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
