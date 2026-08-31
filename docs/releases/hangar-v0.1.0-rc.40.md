## Security and privacy

**Duplicating a project requires administering it.** The new duplication endpoint
re-links a project's custom work item types into the copy, and a type's definition
can be edited by an administrator of any project that links it. Because the person
duplicating becomes an administrator of the copy, allowing a project member to
duplicate would have handed them administrative control over type and property
definitions shared with projects they do not administer and may not belong to. The
endpoint requires the administrator role on the source, and both interface entry
points are gated to match.

The endpoint names its source project in the URL rather than the request body,
because the project-level permission check resolves its subject from the URL. A
body-supplied source would leave an endpoint that reads a project's entire object
graph with no project-level check at all, letting a workspace member copy a project
whose visibility is _Secret_ out of sight of its members. Creating the copy is
authorized separately at workspace level, since holding a role in one project says
nothing about the right to make another.

**A copy never carries another member's private work.** Views whose access is
private and which belong to somebody else are skipped and reported. Membership,
cycles, modules, and views are opt-in rather than default, because copying
membership grants people access to something nobody told them about. Everyone a
copy does enroll is emailed, as they would be if they had been added by hand, and
each role is capped to that person's current workspace role. Anyone who has since
left the workspace is skipped rather than re-enrolled.

**Duplication is rate limited per user and per workspace.** A copy holds a lock on
the workspace row while it runs, so an unthrottled caller could stall project
creation for everyone else in that workspace. The default is 10 per hour per user
and 30 per hour per workspace, both configurable. Admission counts only the views
the requesting person could copy; counting every view would have reported, through
the size-limit error, how many private views other members hold, which no other
endpoint discloses.

**Projects can be duplicated and used as templates.** A copy carries the source's
settings and feature toggles, states including the triage state, work item types,
labels with their hierarchy, estimates, intake configuration, and its cover image.
Members, cycles, modules, and saved views are opt-in. Work items are not copied,
and neither are pages, which are duplicated one at a time by the existing page
action. Duplication is available from the project quick actions in the sidebar,
from the project card menu, from project settings, and from the create-project
dialog as "Start from an existing project".

The cover image is duplicated rather than shared. The asset reference is a single
foreign key, so pointing a copy at the source's row would make deleting either
project take the other's cover with it. The stored file is copied after the
database transaction commits, because an object copy in storage cannot be rolled
back with it; a cover that cannot be copied costs the cover rather than the
project. Saved view filters are translated into the copy's own states and labels,
because a filter carried over unchanged would name the source's rows and silently
match nothing.

**The sidebar no longer crashes when a section is collapsed.** Clicking a project
name in accordion mode, or collapsing the workspace, pinned-items, or favourites
sections, raised `Passing props on "Fragment"!` and replaced the application with
its error screen on every second click. Each of those sections guarded its panel
with a condition that is redundant, because the transition already owns mounting,
and during the closing animation that condition had already become false, leaving
the transition with nothing to attach to. The rich-filters row hit the neighbouring
form of the same fault, where the shared loading component discarded the reference
it was handed.

The repository check that exists to catch this class of fault passed throughout,
because its transition rule accepted any single child rather than requiring one
that is verifiably an element. It now applies the same check its own button and
panel rules already used.

**A committed copy is no longer reported as failed.** Everything after a copy
commits, being the cover, the notifications, and the activity record, ran
unguarded, so a message-broker outage returned an error for a project that had in
fact been created, leaving it to be discovered by accident. Each of those now
fails on its own and is reported in the response summary.

## Migrations and compatibility

**This release adds no database migration.** The schema is unchanged in both
directions, so no reversal is required to roll back.

Two instance settings are added, `PROJECT_DUPLICATE_USER_RATE` and
`PROJECT_DUPLICATE_WORKSPACE_RATE`, defaulting to `10/hour` and `30/hour`. Neither
needs to be set for the feature to work.

The product version is `v0.1.0-rc.40`, the chart version is `0.1.0-rc.40`, the
signed Git tag is `hangar-v0.1.0-rc.40`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.40`. `rc.39` is the immediately previous
complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, `rc.28`, and
`rc.33` were consumed by incomplete publication attempts, and `rc.31` through
`rc.38` are retired; none are upgrade or rollback targets.

## Known limitations and rollback

Hangar `rc.40` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Project duplication copies configuration, not content. Work items are out of scope,
and so are pages. Cycles and modules arrive as empty shells, since there are no
work items to place in them. Webhooks are never copied, because a copied webhook
would begin posting a new project's events to an endpoint whose owner never asked
for them.

Duplication requires administering the source project. Making it available to
project members would mean copying custom work item type definitions into the new
project rather than linking the shared ones, which is a larger change to how a
workspace's types are shared.

The four duplication entry points have been verified by automated interface
contract checks rather than by a person clicking them on a running instance; the
endpoint itself was exercised end to end against live PostgreSQL and object
storage, including the cover image copy.

Rolling back to `rc.39` removes project duplication and restores the sidebar
collapse fault. No schema change needs reversing, and projects that were created
by duplication remain ordinary projects that continue to work in both releases.
