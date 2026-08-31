<!--
Copyright (c) 2026-present Maciej Szymczak and contributors
SPDX-License-Identifier: AGPL-3.0-only
See the LICENSE file for details.
-->

# Duplicating a project

Hangar can copy a project's **configuration** into a new project, so a project
that is set up the way your team works can be used as a template.

This is on for every instance. There is no feature flag and nothing to
configure.

## What a copy contains

| Always copied                                                                                                          | Copied unless you opt out         | Copied only if you opt in                  | Never copied                                                                     |
| ---------------------------------------------------------------------------------------------------------------------- | --------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------- |
| Project settings, feature toggles (cycles, modules, pages, intake, time tracking, work item types) and the cover image | Labels, including their hierarchy | Members and their roles                    | Work items and everything on them — comments, attachments, activity, subscribers |
| States, including the triage state                                                                                     | Estimates and their points        | Cycles, as empty shells                    | Pages                                                                            |
| Work item types                                                                                                        | Intake configuration              | Modules, as empty shells, with their links | Webhooks                                                                         |
|                                                                                                                        |                                   | Views, subject to the privacy rules below  | Published boards, favourites, drafts, notifications, import history              |

The copy always gets a **new name and identifier**, and the person who made it
becomes its project lead and an admin.

### Why some things are not copied

**Work items.** A template is a shape, not a backlog. Copying work items needs
identifier reallocation and a remap of every relation between them; that is a
separate, larger piece of work.

**Webhooks.** A copied webhook would start posting a new project's events to an
endpoint whose owner never asked for them. Re-attach webhooks deliberately.

**Members, by default.** Copying membership grants people access to something
they have not asked for. Ask for it explicitly when you want it. When you do,
everyone the copy adds is emailed, exactly as if you had added them by hand, and
each person's role is capped to their workspace role — a workspace guest cannot
land in the copy holding a member role even if the source says otherwise. That
adjustment is reported as `members:role-adjusted`, and anyone who has since left
the workspace is skipped as `members:not-in-workspace`.

**Someone else's private views.** A view whose access is private and which you
do not own is skipped. The response reports this as `views:private`.

**A lead or default assignee who is not in the copy.** Rather than leaving a
reference to somebody with no access, these are dropped.

Anything skipped is listed in the response's `copy_summary.skipped`.

### Things that are reset rather than carried over

- `external_source` and `external_id` are cleared everywhere. These identify
  rows that came from an import, and a copy is not the same row — carrying them
  over would make a later Todoist re-import skip work it believes it already
  created.
- Cycle progress snapshots, archive timestamps and lock flags start empty.
- Saved view filters are translated into the copy's own states and labels.
  Anything with no counterpart is dropped, reported as `views:unmapped-filters`.

## Who can do it

Two separate permissions, both required:

1. **On the source project** — an active **Admin**. Workspace admins are not
   exempt: an admin who is not a member of the project cannot copy it. This is
   what stops a project whose visibility is _Secret_ being copied out by someone
   who cannot otherwise open it.
2. **In the workspace** — Admin or Member, the same bar as creating any project.

Members and guests cannot duplicate a project. Admin is required rather than
Member because the copy re-links the source's custom work item types, and a
type's definition can be edited by an admin of _any_ project that links it — so
letting a member duplicate would hand them admin control over definitions shared
with projects they do not administer.

## The API

```
POST /api/workspaces/<slug>/projects/<project_id>/duplicate/
```

Every field is optional.

```jsonc
{
  "name": "Marketing (Copy)", // omitted: derived as "<name> (Copy)", then "(Copy 2)" ...
  "identifier": "MKTG2", // omitted: derived from the source's identifier
  "network": 0, // omitted: inherits the source's visibility
  "include": {
    "labels": true, // default true
    "estimates": true, // default true
    "intake": true, // default true
    "members": false, // default false
    "cycles": false, // default false
    "modules": false, // default false
    "views": false, // default false
  },
}
```

`states` and `work_item_types` are always copied and cannot be switched off — a
project without them cannot hold work. An unrecognised key in `include` is
rejected rather than ignored, so a typo cannot silently do nothing.

On success the response is the created project, in the same shape as project
creation returns, plus:

```jsonc
"copy_summary": {
  "source_project_id": "...",
  "counts": { "states": 6, "labels": 12, "members": 1 },
  "skipped": ["webhooks:not-copied"]
}
```

### Errors

| Status | `error`                                   | Meaning                                                            |
| ------ | ----------------------------------------- | ------------------------------------------------------------------ |
| 400    | `PROJECT_NAME_ALREADY_EXIST`              | The name you supplied is taken in this workspace                   |
| 400    | `PROJECT_IDENTIFIER_ALREADY_EXIST`        | The identifier you supplied is taken                               |
| 400    | `PROJECT_ARCHIVED`                        | The source project is archived; restore it first                   |
| 400    | `PROJECT_TOO_LARGE_TO_COPY_SYNCHRONOUSLY` | See below                                                          |
| 429    | —                                         | Rate limited; see below                                            |
| 403    | —                                         | You are not a member of the source, or cannot create projects here |
| 404    | —                                         | No such project in this workspace                                  |

## Size limits

A copy runs in one database transaction inside the request, which keeps it
atomic: either the whole project appears or none of it does. That only holds
while the copy is small. Beyond any of these the request is refused with
`PROJECT_TOO_LARGE_TO_COPY_SYNCHRONOUSLY` and a `detail` object showing the
counts:

- more than 200 members
- more than 500 cycles and modules combined
- more than 5000 rows in total

These are deliberately conservative: past them the transaction holds a lock long
enough to delay other people creating projects in the same workspace. If you are
hitting them, that is the signal to move this work to a background job rather
than to raise the numbers.

## The cover image

The copy gets its own copy of the source's cover, not a reference to it —
`cover_image_asset` is a single foreign key, so sharing the row would make
deleting either project take the other's cover with it.

The file is duplicated after the database transaction commits, because an object
copy in storage cannot be rolled back with it. A cover that cannot be copied is
not worth failing a project over, so the copy is created without one and the
response says `cover_image:failed` (or `cover_image:unreadable` if the source
asset is gone or unreadable).

## Rate limits

The copy holds a lock on the workspace while it runs, so duplication is rate
limited per user and per workspace. Both are configurable:

| Setting                            | Default   |
| ---------------------------------- | --------- |
| `PROJECT_DUPLICATE_USER_RATE`      | `10/hour` |
| `PROJECT_DUPLICATE_WORKSPACE_RATE` | `30/hour` |

The workspace limit is not redundant with the user limit: several people each
staying under their own limit can still stall project creation for everyone else
in the workspace. Exceeding either returns `429`.

## Known limitations

- **Pages are not copied.** Copy them individually with the duplicate action on
  a page, which already handles their attachments.
- **Cycles and modules arrive empty**, since there are no work items to put in
  them.
