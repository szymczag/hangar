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
import ultimately fails, a retry creates a new history record; the failed record
is never reset or overwritten. An explicit retry inherits the prior
idempotency namespace only when the actor, destination, source digest, and
canonical mapping decisions are identical. Such a retry reuses already-created
tasks, sections, and comments, and reports reused and newly imported counts
separately. A changed mapping, actor, destination, or ordinary duplicate import
receives a new namespace and can create additional work items. The duplicate
warning is scoped to the destination project.

Authorization is checked continuously. The initiating account must remain
active and retain workspace-administrator access, and the destination project
must remain available, when the worker claims the job and before every imported
row commits. Revocation stops subsequent writes. A mapped assignee must likewise
remain an active project member; if not, that complete source row fails instead
of silently producing an unassigned task. Reused modules are locked and compared
with the reviewed name, status, and archive state before they are linked.

Starting an import commits the queued job and a durable dispatch record before
contacting the task broker. If broker confirmation is lost, the request still
returns the durable **Queued** job and the dispatcher republishes the same task
identity. This may delay processing, but it does not turn a stored source into a
false failure or delete it prematurely.

Admission is bounded before the source is retained. The default policy permits
one active import per administrator, two per workspace, 50,000 accepted source
rows per workspace in the preceding 24 hours, and 10 MiB of active retained
source data per workspace. A rejected request returns `429` with a stable,
non-sensitive limit code and creates an append-only admission audit event; it
does not upload the source or create a job. API throttles independently limit
preview and execute requests by authenticated user and by server-resolved
workspace identity, so rotating workspace slugs or accounts does not bypass the
corresponding boundary. Each rate boundary is enforced by one atomic
Valkey/Redis operation, so concurrent API replicas cannot admit requests from a
stale cache history. If the throttle store is unavailable, preview and execute
return `503` before parsing the CSV, retaining the source, or creating a job.

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

Database partial unique indexes protect Todoist-created tasks, comments, and
modules against concurrent worker delivery within an idempotency namespace.
Only the transaction that creates an entity emits its creation activity; a
losing or replayed transaction reports reuse instead.

## Operator controls and recovery

`TODOIST_IMPORTS_ENABLED` defaults to `0`. API and worker processes must receive
the same value; keep it disabled while applying migrations or investigating an
import incident. Existing history and reports remain readable while disabled.

The execution and admission controls default to:

| Environment variable                                   |    Default | Accepted runtime range | Purpose                                                           |
| ------------------------------------------------------ | ---------: | ---------------------: | ----------------------------------------------------------------- |
| `TODOIST_IMPORT_LEASE_SECONDS`                         |      `120` |         30–900 seconds | Exclusive worker ownership window                                 |
| `TODOIST_IMPORT_RECOVERY_GRACE_SECONDS`                |       `30` |          0–300 seconds | Delay before an expired owner is fenced and recovered             |
| `TODOIST_IMPORT_SOURCE_RETENTION_HOURS`                |       `24` |            1–168 hours | Maximum configured source retention before reconciliation         |
| `TODOIST_IMPORT_MAX_ACTIVE_PER_USER`                   |        `1` |                  1–100 | Concurrent imports reserved by one administrator in one workspace |
| `TODOIST_IMPORT_MAX_ACTIVE_PER_WORKSPACE`              |        `2` |                1–1,000 | Concurrent imports reserved across a workspace                    |
| `TODOIST_IMPORT_MAX_ROWS_PER_WORKSPACE_24H`            |    `50000` |           1–10,000,000 | Accepted source rows in the preceding workspace 24 hours          |
| `TODOIST_IMPORT_MAX_ACTIVE_SOURCE_BYTES_PER_WORKSPACE` | `10485760` | 1–10,737,418,240 bytes | Source bytes reserved by active workspace imports                 |
| `TODOIST_IMPORT_WORKER_CONCURRENCY`                    |        `2` |                   1–32 | Processes in the dedicated `imports` queue worker                 |
| `TODOIST_IMPORT_WORKER_PREFETCH_MULTIPLIER`            |        `1` |                    1–4 | Broker reservations per import worker process                     |

Request throttles use strict Django REST Framework rate syntax:

| Environment variable                    |     Default | Boundary                             |
| --------------------------------------- | ----------: | ------------------------------------ |
| `TODOIST_IMPORT_PREVIEW_USER_RATE`      | `10/minute` | Authenticated user across workspaces |
| `TODOIST_IMPORT_PREVIEW_WORKSPACE_RATE` | `30/minute` | Workspace across administrators      |
| `TODOIST_IMPORT_EXECUTE_USER_RATE`      |    `3/hour` | Authenticated user across workspaces |
| `TODOIST_IMPORT_EXECUTE_WORKSPACE_RATE` |   `10/hour` | Workspace across administrators      |

Rates must match `<positive integer>/(second|minute|hour|day)`. Invalid integers,
out-of-range values, and invalid rates prevent API and worker startup; Hangar
does not clamp, disable, or silently make these limits unlimited. Throttle state
uses atomic fixed-window counters in the configured Valkey/Redis Django cache
and fails closed with `503` when that dependency is unavailable. Hard admission
reservations and the append-only rolling usage ledger are serialized in
PostgreSQL and remain authoritative under concurrent requests.

Todoist work is routed only to the `imports` Celery queue. Run at least one
dedicated import worker with `HANGAR_WORKER_QUEUE=imports`; general and email
workers do not consume that queue. Beat must run for durable broker redispatch,
lease recovery, and source cleanup. Disabling Beat leaves new jobs durable but
can prevent automatic recovery.

Importer transitions also create append-only audit events containing identifiers,
states, generations, safe reason codes, and counts. They never contain CSV rows,
filenames, object keys, source digests, mapping contents, or raw exceptions.
Quota rejection events intentionally have no job identifier because admission
was denied before a job existed.

Monitor the oldest pending dispatch, import queue depth, active jobs by state,
expired leases, recovery and lease-loss counts, quota/throttle denials, terminal
duration/result, source-cleanup age, and deletion failures. Alert when a pending
dispatch exceeds five minutes, a lease expires without recovery, a source
survives its retention deadline plus cleanup grace, cleanup repeatedly fails, or
workspace denials spike. During an incident, disable `TODOIST_IMPORTS_ENABLED`
on API, import-worker, and Beat workloads together; preserve PostgreSQL audit and
job records, then diagnose the broker, cache, database, and private bucket
without logging source rows, filenames, object keys, mappings, digests, or raw
exceptions.
