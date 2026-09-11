## Security and privacy

**Workshop sessions are editable again, and in every view of a work item.** The
session editor sat in the properties panel, which is a quarter of the viewport
wide and spends a fixed 120px of that on its label column. Each session rendered
as seven stacked rows, so a three-session workshop produced twenty-one of them,
against date inputs the browser will not shrink below roughly the space left.
Sessions now have their own full-width section beside sub-work-items and links,
and the properties panel carries a summary that scrolls to it. The editor was
also reachable only from the full page: a workshop opened from a board or a list
showed no session UI at all, and now shows the same section the full page does.

**Capacity is three pages instead of one.** `/capacity` is your own trainer
settings -- booking hours, the calendars that block your time, the Google
connection. `/capacity/team` is the workspace ledger: who has time, and how it is
already booked. `/capacity/planner` is workshop planning. They were one page
holding all three, where a personal action and an administrative one shared a
single control, and where opting in as a trainer lived inside a table about
everybody else.

**Editing another trainer's schedule is an administrator's action, and now looks
like one.** It opens over the team page rather than pushing the ledger down, and
it no longer shares state with a trainer editing their own hours. The server
already refused the first to anyone but an administrator; the interface now says
so as well.

**The planner can look past the week on screen.** "Find first available" walks
forward a fortnight at a time until it finds the first slot the whole trainer
block fits into, and each trainer has a "When?" that asks the same question about
that person alone. It searches one window at a time on purpose: the capacity
endpoint is rate-limited per person and per workspace, and asking for four months
at once is how a workspace gets refused. It stops after roughly four months and
says so rather than searching indefinitely.

## Migrations and compatibility

This release adds no migrations, changes no API contract, and touches no chart
resources, Secrets, storage, RBAC, NetworkPolicies, public routes or
configuration values. The only backend file that changed is the visual-test seed,
which never runs outside the test stack.

`/capacity` keeps its address and changes what it shows: the ledger and the
planner moved to `/capacity/team` and `/capacity/planner`, and all three have
their own entry in the sidebar. A bookmark still resolves.

Everything in this release is in the web application, so an older API serves it
unchanged.

## Known limitations and rollback

Rolling back to `rc.50` restores the unreadable session editor and returns the
capacity page to one page holding three concerns. Nothing here writes schema, so
a rollback is a matter of returning the web image to `rc.50`.

The team ledger's timeline grid overflows its container on a 1440-wide window:
the day-capacity column, the manage-schedule links and the timezone note are
clipped. This is not new in this release -- the markup is unchanged -- but it is
now recorded in a baseline rather than going unnoticed, and it is worth fixing.

Week selection does not carry between `/capacity/team` and `/capacity/planner`.
Each opens on the current week.

The instance console's second-factor screens remain outside the visual suite.
They are gated on a browser API that requires a secure context, which the suite's
stack does not serve.

The evaluation profile remains qualified on AMD64 only. The production profile
remains unsupported, and no new live-cluster qualification has yet been completed
for this release candidate.
