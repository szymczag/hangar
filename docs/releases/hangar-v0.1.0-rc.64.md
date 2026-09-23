## Security and privacy

**A shared training calendar can no longer block a trainer's time.** Such a
calendar carries the whole organization's training, so a trainer who picked it as
one of their blocking calendars filled their own week with other people's
workshops — and told everyone reading the ledger that they were busy when they
were not. Their own trainings are already blocked by recognition, from their own
invitations, so the calendar is now marked in the list, cannot be ticked, and is
refused by the API. The refusal lives on the server because the list is only the
polite half of it.

What makes that possible is a flag on each calendar in the picker saying whether
a workspace rule already reads it as training. It is derived per request from the
rules, never stored, and tells the trainer nothing they could not already see:
these are their own calendars, and they hold the invitations.

No other change alters what is read, written, stored or shown. Titles are still
read only for events a rule matched, the availability path still never asks Google
for event summaries, and no calendar identifier, address or name enters a log.

## Migrations and compatibility

Upgrade from `0.1.0-rc.63`. This release carries **three database migrations**,
all in the `ext` application, and the ordinary release Job applies them.

**Workshops are offered only by projects that ask for them.** Until now the type
arrived in every project the moment anybody in the workspace became a trainer,
which put a training-specific type in the picker of projects that have nothing to
do with training. A project now opts in from **Project settings → Work item
types**, and only its administrators decide. Migration `0037` keeps the type in
every project that already holds a Workshop and withdraws it from the rest, which
can turn it back on whenever they like. Nobody loses a workshop, and no project
suddenly refuses a type it is using.

**A Workshop now carries three roles: Sales, PM and Trainers.** Migration `0038`
adds them as member properties, to the types that already exist as well as to new
ones. They are ordinary properties a coordinator can rename, reorder and require;
each also carries a system key, so renaming a column does not hide the trainers
from the planner, the checklists or the calendar import. Removing one is refused.

**Delivery is tied to the trainer property**, which is why that one has
consequences. Sessions start from it and may still override it one session at a
time, the checklist's "the workshop's trainer" mode resolves to the people it
names, and naming somebody assigns them to the work item — which is how the
ledger, the planner and the schedule editor keep working unchanged instead of each
learning about a new field. Somebody who cannot hold work in the project is
reported rather than assigned, and dropping somebody from the property leaves
their assignment alone, because they may still hold subtasks. A workshop that
predates the properties falls back to its assignees everywhere the trainers are
asked for.

**The default working week is a working day and an evening**, 09:00–17:00 and
19:00–22:00 on weekdays, in place of a single 09:00–22:00 block that offered
thirteen unbroken hours and made the planner look as though the whole team was
free every evening. Migration `0039` moves trainers who never set their hours onto
it, and only those: the revision counter is what tells an untouched schedule from
somebody who chose those hours on purpose. The counter itself is left alone,
because this is Hangar changing its own assumption rather than the trainer
changing theirs.

**Importing a training two people run creates one workshop, not two.** The import
groups the invitations that describe one training rather than treating each
trainer's copy as its own event, puts every trainer on the single session, and
fills the trainer property from the invitation. Importing the rest of a partly
imported training joins the workshop that exists instead of standing a second one
beside it.

**The team ledger shows the working week.** Monday to Friday, with **Show
weekends** bringing the other two back; like the layer filter, the choice lives in
the URL, so a link to that Saturday carries the weekend with it. In My capacity,
the calendars that are neither the primary one nor already chosen start folded
away — a Google account carries holidays, birthdays, subscriptions and whatever a
colleague once shared.

The training report screen was taken apart along its own seams and is now
photographed by the visual suite, so a change to it has to be looked at.

Rolling back past `0037` is safe in form: the older build re-adds the Workshop
type to every project on its own the next time it provisions system types, which
is the behaviour this release removes. Rolling back past `0038` drops the three
role properties and the values recorded in them; rolling back past `0039` restores
the old default for the same untouched profiles.

Product version is `v0.1.0-rc.64`, Git tag `hangar-v0.1.0-rc.64`, Helm chart
version `0.1.0-rc.64`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.64`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.63` are unchanged: recognition depends on
trainers holding their own copy of each invitation, a trainer who has not granted
training recognition is reported as such rather than as having run no training,
and calendar write-back depends on one person's token remaining healthy.

Two limitations are new with this release.

Turning Workshops off in a project is refused while the project still holds any,
because those work items would be left with a type their own project no longer
offers. Move them or change their type first.

The trainer property assigns but never unassigns. Somebody removed from it stays
an assignee of the workshop until a person removes them, which is deliberate —
they may still hold subtasks — but it does mean the assignee list can name more
people than the property does.

Trusted Types still ship observing rather than enforcing. This release removes a
source of false alarms in the bundle contract that guards them: a sink in a chunk
without a source map used to be attributed to the chunk's own file name, which is
build output, so the reviewed inventory gained and lost entries between builds and
the check failed at random. Such a chunk is now named and the scan stops.
