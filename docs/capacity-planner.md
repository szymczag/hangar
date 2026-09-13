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
