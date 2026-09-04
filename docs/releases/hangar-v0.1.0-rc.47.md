## Security and privacy

**Booking hours now describe the window in which a trainer may be booked.** New
and previously empty schedules default to Monday through Friday, 09:00–22:00.
The capacity page presents a compact summary until Manage schedule is opened,
where each weekday remains editable. Existing non-empty weekly schedules are
preserved.

**Google Calendar is the source of busy-time exceptions.** The separate schedule
exceptions feature and API representation have been removed. After a new Google
Calendar connection, Hangar selects the account's Primary calendar automatically
when no selection exists. Trainers may deselect it, select additional personal or
work calendars, and must retain at least one blocking calendar.

**The capacity view is clearer and more resilient.** Anonymous Google busy time
and scheduled workshops render above the booking-hours layer. Capacity requests
coalesce concurrent refreshes, bound retries, honour `Retry-After`, and keep the
last successful timeline visible during transient rate limiting. Default admission
limits increase to `20/minute` per user and `60/minute` per workspace.

**Workshop can be selected when creating or editing a work item.** The work-item
modal now renders the project type selector, including the canonical Workshop type
when capacity is active. Workshop scheduling remains available in the issue
sidebar and requires every assignee to have an active trainer profile.

## Testing

Project description-image copying now has a real object-storage integration test.
The test writes and reads an object through MinIO using an independent client,
proves that the copied asset uses a different object key, and verifies that a
member of the copied project can read the copy without gaining access to the
source asset. The storage suite is part of the aggregate API gate.

## Migrations and compatibility

Migration `ext.0021_booking_hours` updates only semantically empty trainer weekly
schedules to Monday–Friday, 09:00–22:00 and increments their schedule revision.
It changes the model default and removes the trainer schedule-exception table.
All existing exception rows are intentionally deleted; operators must represent
future exceptions as events in one of the selected Google calendars.

The chart does not add Kubernetes resources, Secrets, storage, RBAC,
NetworkPolicies, or public routes. Its capacity rate defaults change from
`10/minute` and `30/minute` to `20/minute` and `60/minute`. Explicit operator
overrides remain unchanged. Deploy all application images as one release unit and
wait for the migration Job before admitting traffic.

## Known limitations and rollback

Google busy events are deliberately anonymous in the capacity view. A Google
Calendar event blocks availability but does not become a Plane work item or a
named workshop. To display a training item, create a Workshop work item, assign
active trainers, and configure its workshop schedule.

Rollback to `rc.46` cannot reconstruct deleted schedule-exception rows. Reversing
the migration may recreate an empty table, while schedules populated with the new
default remain populated because the data migration has no destructive reverse
operation. Take a PostgreSQL backup before upgrading and prefer a forward fix. If
the deleted exception data is required after rollback, restore that backup.

The evaluation profile remains qualified on AMD64 only. The production profile
remains unsupported, and no new live-cluster qualification was performed for this
release candidate.
