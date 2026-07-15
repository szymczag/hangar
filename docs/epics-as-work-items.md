# Epics as work items

Hangar models an Epic as a level-1 work item type. An Epic is created, listed,
filtered, opened, and updated through the same Work Items surfaces as a Task or a
custom type. It is not a separate project feature or a separate collection in the
web application.

This page explains the user workflow, the hierarchy rules, and the compatibility
contract for installations upgrading from the earlier dedicated Epic feature.

## Task and Epic provisioning

New projects receive the canonical system types automatically. Upgraded projects
receive them during migration. If either type is missing or damaged, a project
administrator can repair both from **Project settings → Work item types**:

| System type | Level | Default | May have a parent |
| ----------- | ----- | ------- | ----------------- |
| Task        | 0     | Yes     | Yes               |
| Epic        | 1     | No      | No                |

The repair operation is idempotent. Repeating it does not create duplicate system types.
It also restores the canonical levels and default selection if an older deployment
left inconsistent metadata.

System identity, hierarchy level, and default semantics cannot be changed through
the issue-type API. Display fields, such as the type name and description, can be
edited. Task and Epic cannot be deactivated or deleted. Administrators can add
custom level-0 types after the system types have been enabled.

`IssueType.system_key` is the stable identity for the two system types.
`ProjectIssueType` is authoritative for whether a type is available to a project,
its project level, and the project default. The older `is_epic`, `is_default`, and
`level` fields on `IssueType` remain as constrained compatibility mirrors; clients
cannot write them for system types.

## Create and find an Epic

1. Open the project’s **Work Items** page.
2. Create a work item with the normal create action.
3. Set **Work item type** to **Epic**.
4. Enter the remaining fields and create the work item.

The Epic appears in the ordinary Work Items list. Use the work-item type filter to
show only Epics. Existing saved views and links to an individual work item continue
to use the normal work-item route.

The former project-sidebar **Epics** item is intentionally absent. Visiting the old
web `/epics` route redirects to the project Work Items page.

## Build a hierarchy

An Epic can be the parent of Tasks and other level-0 work items. Use the normal
sub-work-item action from the Epic detail or peek view.

Hangar enforces these invariants on the server, independent of the client:

- an Epic cannot have a parent;
- a work item cannot be its own parent;
- a parent change cannot create a direct or indirect cycle;
- parent and child must belong to the same project and workspace;
- a multi-item attachment is atomic—one invalid identifier rejects the complete
  request;
- one request can attach at most 100 sub-work-items and hierarchy depth is capped
  at 100 levels;
- concurrent hierarchy changes are serialized per project and lock the affected
  work-item rows.

Parent ancestry is evaluated by one bounded, parameterized recursive database
query. Validation cost therefore does not grow into one application/database
round trip per ancestor.

Type assignment and direct parent-change checks apply to both the authenticated
application API and the public API. The authenticated sub-work-item endpoint adds
the atomic multi-item checks. Together they prevent clients from bypassing the
hierarchy through a direct request or by reusing a work-item identifier from
another project.

## API reference

Use the standard project work-item endpoints for new integrations. Set `type_id` to
the project’s active Epic type when creating or updating a work item. Work-item
responses expose both `type_id` and the derived `is_epic` value.

Project type management is available under:

```text
GET  /api/workspaces/{workspace_slug}/projects/{project_id}/issue-types/
POST /api/workspaces/{workspace_slug}/projects/{project_id}/issue-types/enable/
```

The enable endpoint requires project-administrator permission. Type assignment is
accepted only when the type is active and linked to the target project.
Standard detail, sub-work-item, archive, cycle, module, and intake surfaces all
include Epic work items; there is no separate manager-level collection.

The older `/epics`, `/v2/epics`, and Epic sub-resource endpoints remain as server
compatibility adapters. They preserve Epic-only collection scoping and force the
canonical Epic type on legacy create requests. New clients must not depend on these
routes; they are retained to support upgrades and older integrations while the
normal Work Items API is the source of truth.

The web application does not maintain an Epic collection, service, or detail store.
Compatibility store names resolve to the ordinary project Work Items store so
extensions compiled against the former interface do not create a second state graph.

## Upgrade behavior

Database migration `0127_issue_type_system_keys` assigns stable `task` and `epic`
system keys. It provisions every active project, including projects that did not
previously enable work-item types. The migration:

- reuses the oldest active workspace Epic type when possible;
- creates a distinct canonical Task type and does not convert a user-defined type
  merely because it is named `Task`;
- links Task at level 0 and Epic at level 1;
- makes Task the project default and clears conflicting default links; and
- assigns the canonical Task type to existing untyped work items.

Workspace seed and dummy-data jobs also provision the system types before they
create projects or work items, so post-upgrade maintenance jobs cannot reintroduce
untyped records.

On PostgreSQL, the migration commits its atomic data-provisioning operation before
building the new type constraints. This operation boundary is required so deferred
foreign-key triggers are settled before the partial unique index is created. If the
constraint step fails, correct the database condition and rerun the migration; the
idempotent provisioning step safely repairs the same rows again.

Existing work items, Epic relationships, comments, attachments, activities, and
custom property data are retained. The migration does not delete legacy type rows.

Back up PostgreSQL before upgrading. The schema migration is reversible, but its
data-provisioning step is intentionally not destructive on rollback: created type
rows, project links, and backfilled work-item type assignments remain. Restore the
pre-upgrade database backup if an exact data rollback is required.

## Troubleshooting

If **Epic** is missing from the create form, open **Project settings → Work item
types** and confirm that Task and Epic are listed. A project administrator can use
**Enable work item types** to provision or repair them.

If an Epic does not appear, clear the work-item type filter and check the ordinary
Work Items page. The dedicated Epic page is no longer a separate data source.

If the API rejects `type_id`, confirm that the type returned by the project’s
issue-type endpoint is active and belongs to that same project. Type identifiers
from another project are rejected even when both projects belong to one workspace.
