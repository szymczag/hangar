## Security and privacy

**The workshop planner no longer finds a slot it cannot let you take.** A plan
stored the fortnight the coordinator happened to have on screen when they saved
it, and a hold had to fall inside that window -- so stepping the week marked the
plan unsaved, every candidate fell back to "save this version of the plan
first", and saving is refused outright while a hold is active. The planner could
report the first opening six weeks out and then offer no way to reserve it. The
week was never plan data; it is what you are looking at, and it already lives in
the page's own `week` parameter.

**The planner offers a choice of times, not one.** It used to take the first
moment each free opening began and stop there, so a trainer free from nine to
five produced a single card at nine, and "could she do it after lunch?" could not
be asked at all. Starts now step through each opening on the half hour, up to
four per trainer per day, spread across the day rather than bunched at its start,
with a control to narrow to mornings or afternoons. An opening that begins at an
odd minute -- where a calendar block closed -- still offers that exact moment
first, because it is the genuine earliest fit and "find first available" reads
it.

**A held slot can become a session on the work item it was planned for.** The
planner could answer who and when, and then had nowhere to put the answer: the
trainer and the times were retyped into a Workshop work item by hand, and the
hold stayed put, blocking that trainer for its full seventy-two hours on top of
the session just created from it. A plan is now attached to a Workshop work item,
and scheduling writes the session, assigns the trainer and spends the hold in one
step. The availability check that guarded the hold runs again at that moment
rather than being trusted -- three days is long enough for the same trainer to be
booked elsewhere -- and a refusal leaves the hold intact, so the slot is not lost
along with the attempt.

**The "about this build" dialog names the build it is in.** It read the release
notes bundled at build time, and that bundle had not been regenerated since
`rc.51`, so `rc.52` and `rc.53` both shipped a dialog naming a release two
behind. The check that catches this was already failing when `rc.53` was cut;
both are fixed here, and the dialog on this build reads `rc.54`.

## Migrations and compatibility

**A workshop plan no longer stores the week it was planned in.** Migration
`ext.0025` drops `window_starts_at` and `window_ends_at` from
`ext_workshop_plan_drafts`, with the check constraint over them. `POST` and `PUT`
on `/api/workspaces/<slug>/capacity/plans/` no longer require or return the two
fields, and a client that still sends them is unaffected: they are ignored rather
than rejected. Holds keep every conflict check they had, and gain one -- a block
that has already started is refused.

**A workshop plan now points at the work item it is for.** Migration `ext.0026`
adds a nullable `issue` to `ext_workshop_plan_drafts`, and records two new
enumerated values -- a `scheduled` hold status, so a hold that became a session
is distinguishable in the audit trail from one that was let go, and a matching
`plan.scheduled` audit action. Neither alters existing rows.

Two endpoints are new: `POST /api/workspaces/<slug>/capacity/plans/<id>/schedule/`
turns the active hold on a plan into a session on its work item, and
`GET /api/workspaces/<slug>/capacity/workshops/` lists the Workshop work items
the caller may plan against. `issue_id` is accepted and returned by the existing
plan endpoints; it is optional and defaults to null, so a client that does not
know about it behaves exactly as before.

Beyond those two migrations this release changes no other API contract, and
touches no chart resources, Secrets, storage, RBAC, NetworkPolicies, public
routes or configuration values.

The capacity pages keep their addresses, and the planner keeps reading its week
from the `week` query parameter, so an existing link resolves exactly as before.

## Known limitations and rollback

Rolling back to `rc.53` is a matter of returning the images to it. Both
migrations reverse with saved plans in the table.

`ext.0026` reverses by dropping the column it added, so a plan loses the work
item it was attached to and becomes an ordinary exploratory plan again. Sessions
already written to work items are untouched -- they are real sessions, not a view
of the plan that produced them. A hold left in the `scheduled` state reads as an
unknown status to `rc.53`, which matches only `active` when it counts a block
against a trainer, so a spent hold is not reserved a second time.

`ext.0025` reverses by restoring the columns it dropped: each draft is given the
fortnight beginning when it was created, because the window it originally carried
was deliberately discarded and cannot be recovered. A plan saved long enough ago
therefore reopens on `rc.53` showing a window in the past, which that version
already handles -- the coordinator steps to the week they want and saves.

Two limitations recorded against `rc.51` are resolved beyond those `rc.53`
closed: the planner can look past the week on screen and act on what it finds,
and its result is no longer a dead end.

The planner's newer surfaces are not photographed. The visual suite covers the
planner as it first opens, but not a plan with a hold on it, and so not the
scheduling step either -- that needs a held plan in the visual fixtures. Nothing
on a work item says which plan a session came from; the audit trail records it
and the interface does not. A hold still expires silently at seventy-two hours,
with no warning that a slot is about to be given back.

The peek panel's workshop-session baseline compares exactly, with no pixel
tolerance, and varies between runs on some local machines through antialiasing on
rounded corners alone. It has been stable in continuous integration, where
rendering is deterministic, but a local suite run may report it as failing when
nothing has changed.

The instance console's second-factor screens remain outside the visual suite.
They are gated on a browser API that requires a secure context, which the suite's
stack does not serve.

The evaluation profile remains qualified on AMD64 only. The production profile
remains unsupported, and no new live-cluster qualification has yet been completed
for this release candidate.
