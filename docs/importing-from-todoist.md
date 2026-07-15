# Import a Todoist CSV export

Workspace administrators can import a Todoist project export into an existing
Hangar project. The importer previews the file first, lets you resolve identity
and module mappings, then creates the work in a background job.

The importer is disabled by default. An operator must provision the dedicated
private import bucket, confirm that API and worker processes share the same
configuration, and set `TODOIST_IMPORTS_ENABLED=1` before it appears in
**Workspace settings**. Leave the flag disabled during maintenance or whenever
the private bucket is unavailable. Disabling it immediately rejects new preview,
start, and cancellation requests and prevents queued workers from mutating data;
existing history and reports remain available for recovery and audit.

## Before you begin

You need:

- an instance where the operator has enabled Todoist imports;
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
   **Preparing**, **Queued**, **Processing**, and **Cancelling** are active
   states. You can cancel a preparing, queued, or processing job. A queued job
   stops immediately; a processing cancellation takes precedence over a worker
   completion and becomes terminal at the next cooperative boundary.
5. When the job finishes, select **Download report** to review totals and any
   row-level errors.

An interrupted job is retried automatically with bounded backoff. Each internal
attempt has a new durable dispatch identity and execution generation, so a stale
or duplicate worker cannot claim ownership or overwrite the final result. If an
import ultimately fails, uploading the file again creates a new history record;
the failed record is never reset or overwritten. Until the history explicitly
reports reused entities, treat a new attempt or a confirmed exact-file duplicate
as capable of creating additional work items. The duplicate warning is scoped to
the destination project.

Starting an import commits the queued job and a durable dispatch record before
contacting the task broker. If broker confirmation is lost, the request still
returns the durable **Queued** job and the dispatcher republishes the same task
identity. This may delay processing, but it does not turn a stored source into a
false failure or delete it prematurely.

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
source when processing finishes. A reconciler runs every five minutes and fences
expired execution ownership before removing a source whose 24-hour retention
deadline has passed. Failed object deletion remains retryable and the database
record keeps the source reference until storage confirms deletion.
Import history and downloaded reports contain counts and safe diagnostics, not
the original row contents or import configuration.

## Operator controls and recovery

`TODOIST_IMPORTS_ENABLED` defaults to `0`. API and worker processes must receive
the same value; keep it disabled while applying migrations or investigating an
import incident. Existing history and reports remain readable while disabled.

The execution controls default to:

| Environment variable | Default | Accepted runtime range | Purpose |
| --- | ---: | ---: | --- |
| `TODOIST_IMPORT_LEASE_SECONDS` | `120` | 30–900 seconds | Exclusive worker ownership window |
| `TODOIST_IMPORT_RECOVERY_GRACE_SECONDS` | `30` | 0–300 seconds | Delay before an expired owner is fenced and recovered |
| `TODOIST_IMPORT_SOURCE_RETENTION_HOURS` | `24` | 1–168 hours | Maximum configured source retention before reconciliation |

Invalid non-integer values prevent API/worker startup instead of silently
disabling ownership or retention controls. Values outside the accepted range are
clamped to the documented safety boundary. Beat must run for durable broker
redispatch, lease recovery, and source cleanup; disabling Beat leaves new jobs
durable but can prevent automatic recovery.

Importer transitions also create append-only audit events containing identifiers,
states, generations, safe reason codes, and counts. They never contain CSV rows,
filenames, object keys, source digests, mapping contents, or raw exceptions.
