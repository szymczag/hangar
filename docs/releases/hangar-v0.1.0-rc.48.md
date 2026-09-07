## Security and privacy

**Workshop planning finds trainers without exposing calendar event details.** A
coordinator can define the workshop title, duration, preparation and travel time,
candidate trainers, and a delivery window. Hangar compares that request with
booking hours, anonymous Google busy intervals, confirmed workshops, and active
planning holds, then presents viable trainer/time combinations. Google event
titles, attendees, descriptions, and locations remain outside Hangar.

**Saved drafts and expiring holds support safe coordinator hand-offs.** Planner
inputs can be saved per workspace and owner with optimistic revision checks.
Coordinators may place a short-lived hold on a proposed trainer and time. Active
holds block competing proposals; release and expiry restore availability. Draft
and hold mutations are workspace-authorized, CSRF-protected, validated on the
server, and recorded in the immutable capacity audit log.

**Multi-session workshops assign logistics precisely.** A Workshop work item may
contain multiple ordered sessions. Each session has its own start, end,
preparation, travel-before, travel-after, and trainer selection. Existing
single-session schedules are migrated without changing their time or logistics,
and their current issue assignees become the migrated session's trainers.

**Scheduling surfaces are easier to scan.** The work-item sidebar presents each
session as normal detail fields instead of a compressed table. The capacity page
separates booking hours, calendar conflicts, workshops, and planning holds, and
the planner ranks concrete options for coordinators. The visual-regression suite
now exercises Hangar's running web, admin, and workspace surfaces in CI.

## Migrations and compatibility

Migrations `ext.0022_workshop_sessions`, `ext.0023_workshop_plan_drafts`, and
`ext.0024_workshop_plan_holds` add session, draft, and hold tables. Migration
`0022` creates one position-zero session for every non-deleted existing workshop
schedule, copies its time and logistics values, and assigns the issue's current
non-deleted assignees. The legacy schedule fields remain populated for contract
compatibility. Migrations `0023` and `0024` create new tables and audit actions;
they do not rewrite existing planner or calendar data.

The chart adds no Kubernetes resources, Secrets, storage, RBAC, NetworkPolicies,
public routes, or configuration values. Deploy the web and API images together
and wait for the revision-scoped migration Job before admitting traffic. Mixed
`rc.47` and `rc.48` web/API versions are unsupported because the workshop
schedule and planner contracts changed together.

## Known limitations and rollback

Planner holds are coordination aids, not customer bookings or Google Calendar
events. A hold expires automatically and must be converted into a Workshop work
item through the normal confirmation workflow. Drafts are private to their owner;
other coordinators cannot edit or resume them.

Rolling back application images to `rc.47` leaves the new session, draft, and hold
tables in PostgreSQL. The old application ignores them, but workshops edited with
multiple sessions cannot be represented faithfully by the legacy single-session
UI. Release active holds before rollback, export any planner state that must be
retained, and prefer a forward correction. If an emergency rollback is required,
return every application image to `rc.47` as one unit; do not reverse migrations
unless a separately tested data-conversion plan exists.

The evaluation profile remains qualified on AMD64 only. The production profile
remains unsupported, and no new live-cluster qualification has yet been completed
for this release candidate.
