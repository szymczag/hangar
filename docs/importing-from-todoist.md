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
file. It shows separate task, section, note, warning, and error counts. Expand
the diagnostics to review every skipped row. If errors are present, you must
explicitly confirm that valid rows may be imported while those rows are skipped.

## Review mappings

For each source assignee, choose an active destination-project member. Leave an
identity unmapped to create those tasks without an assignee. Hangar does not
guess identities from names or email-like text.

Todoist sections become Hangar modules. If a section has the same name as an
existing module, explicitly choose whether to reuse it or create a module under
a unique replacement name. Importing sections enables the Modules feature for
the destination project. Duplicate section names inside the source file are
reported as row errors rather than merged implicitly.

A Todoist project note becomes the destination project's description only when
that description is empty. Existing project descriptions are never overwritten.

## Start and monitor the import

1. Resolve every module-name conflict.
2. If the preview identifies an exact duplicate, explicitly confirm that you
   want to import it again.
3. Select **Start import**.
4. Follow progress under **Recent imports**.
   You can cancel queued or processing jobs; processing cancellation takes
   effect at the next safe batch boundary.
5. When the job finishes, select **Download report** to review totals and any
   row-level errors.

An interrupted job is retried automatically with backoff. If it ultimately
fails, uploading the same file again reuses that job identity and the objects
already created by its earlier attempts, so the retry does not duplicate them.
A completed or partially completed exact-file import is different: confirming
the duplicate warning starts a new job and can intentionally create another set
of work items. The warning is scoped to the destination project.

The history distinguishes **Completed** from **Completed with errors**. Reports
are downloadable only after a job reaches a terminal state and are returned
with no-store response headers.

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
import, Hangar stores the source temporarily in a dedicated private object
storage bucket that is not routed through the public application endpoint. An
upload fails closed if an anonymous object lookup succeeds. Hangar removes the
source when processing finishes and also runs a daily cleanup for sources older
than 24 hours.
Import history and downloaded reports contain counts and safe diagnostics, not
the original row contents or import configuration.
