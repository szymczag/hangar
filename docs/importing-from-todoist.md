# Import a Todoist CSV export

Workspace administrators can import a Todoist project export into an existing
Hangar project. The importer previews the file first, lets you resolve identity
and module mappings, then creates the work in a background job.

## Before you begin

You need:

- workspace administrator access;
- a destination project that already exists; and
- a CSV file exported from Todoist using UTF-8 encoding.

The importer accepts files up to 5 MiB and 10,000 rows. Keep an untouched copy
of the export until you have reviewed the completed import report.

## Preview the import

1. Open **Workspace settings > Imports**.
2. Choose the destination project.
3. Select one Todoist CSV export.
4. Select **Preview import**.

The preview validates the schema without creating work items or retaining the
file. It shows the number of tasks, sections, notes, and warnings that the job
will process.

## Review mappings

For each source assignee, choose an active destination-project member. Leave an
identity unmapped to create those tasks without an assignee. Hangar does not
guess identities from names or email-like text.

Todoist sections become Hangar modules. If a section has the same name as an
existing module, keep its name to reuse that module or enter a unique name to
create another one. Importing sections enables the Modules feature for the
destination project.

A Todoist project note becomes the destination project's description only when
that description is empty. Existing project descriptions are never overwritten.

## Start and monitor the import

1. Resolve every module-name conflict.
2. If the preview identifies an exact duplicate, explicitly confirm that you
   want to import it again.
3. Select **Start import**.
4. Follow progress under **Recent imports**.
5. When the job finishes, select **Download report** to review totals and any
   row-level errors.

Imports create new work items; they do not update existing work. Retrying the
same export can therefore create duplicates. The exact-file warning is scoped
to the selected destination project.

## Field mapping and limitations

| Todoist data         | Hangar result                                   |
| -------------------- | ----------------------------------------------- |
| Task content         | Work-item title                                 |
| Description          | Sanitized rich-text description                 |
| Priority 1–4         | Urgent, high, medium, or none                   |
| Section              | Module                                          |
| Indentation          | Parent/child work-item relationship             |
| Task note            | Work-item comment                               |
| Responsible identity | Explicitly mapped project member, or unassigned |
| Date                 | Target date                                     |
| Date and deadline    | Start date and target date                      |
| Project note         | Project description, only when empty            |

Recurring schedules, times, time zones, and durations cannot be represented
directly. Hangar preserves those values in an imported comment and includes a
warning in the report. Invalid rows fail independently, so valid rows can still
be imported.

## Source-file privacy

Preview requests are parsed in memory and are not retained. After you start an
import, Hangar stores the source temporarily in private object storage, removes
it when processing finishes, and also runs a daily cleanup for stale sources.
Import history and downloaded reports contain counts and safe diagnostics, not
the original row contents or import configuration.
