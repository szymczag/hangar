## Security and privacy

`rc.9` makes Todoist imports opt-in and adds defense in depth around every import
mutation and worker transition. Workspace-administrator authorization is
revalidated at use time, project and module bindings are checked inside the write
transaction, immutable manifest digests bind execution to the accepted request,
and expiring leases fence stale or duplicated workers. Database uniqueness
constraints make task, comment, and module creation idempotent under broker
redelivery and concurrent execution.

Atomic Valkey-backed request throttles and PostgreSQL-backed user/workspace
admission budgets bound active jobs, retained source bytes, and accepted rows in a
rolling 24-hour window. Cache failure rejects new mutations before parsing or
retaining source data. The private import bucket remains outside public routing,
source deletion is reconciled after terminalization or lease expiry, and audit and
retry history expose stable reason codes rather than CSV contents, object keys,
configuration, source digests, or raw exceptions.

Runner API failures no longer return internal exception details. The incorporated
upstream asset authorization fix also scopes project asset reads, updates, and
deletes to project membership. Deployment status shown for telemetry and Amazon
SES remains read-only and does not expose configured endpoints or credentials.

## Migrations and compatibility

This release applies Django database migrations `db.0125` and `ext.0007` through
`ext.0010`. Migration `db.0125` rejects existing duplicate active Todoist external
IDs before creating concurrent partial unique indexes for tasks, comments, and
modules. Treat that rejection as a data-integrity incident: preserve the rows,
determine the authoritative records, and resolve duplicates through a reviewed
procedure before retrying the migration.

Migration `ext.0007` adds the fenced import state machine, execution leases,
manifest and idempotency metadata, retention deadlines, retry lineage, dispatch
records, and append-only audit events. Existing queued or processing jobs are
failed with the safe reason `security_upgrade_required`; their retained execution
configuration and broker task identifiers are cleared. Migrations `ext.0008`
through `ext.0010` add and backfill serialized user/workspace admission budgets,
quota-denial auditing, and the rolling usage ledger.

Before upgrading from `rc.8`, prevent new administrator import mutations, allow
existing imports to reach a terminal state, and take a coordinated PostgreSQL and
object-storage backup. The target chart keeps Todoist imports disabled unless
`todoistImports.enabled=true`; enabling them requires the private import bucket,
Valkey, PostgreSQL, RabbitMQ, a dedicated `imports` queue worker, and the single
Beat scheduler. Kubernetes 1.30 through 1.36, Helm 4.2, `linux/amd64`, Restricted
Pod Security Admission, TLS ingress with WebSocket support, a
`NetworkPolicy`-enforcing CNI, and persistent storage remain the qualified
boundary. Production support remains unavailable.

## Known limitations and rollback

Todoist imports remain additive: cancellation, retry, or rollback does not delete
work items already committed to a project. A job failed by the security migration
is not resumed in place; after reviewing its history and resulting project state,
an administrator may submit an explicit retry under the new execution controls.
Recurring schedules, time zones, and durations are still retained as metadata
rather than native scheduling rules. Source deletion depends on object-storage
availability and remains retryable until storage confirms deletion.

Do not roll application images back to `rc.8` against a database migrated by
`rc.9`. The new constraints, transformed import-job state, admission ledgers, and
worker protocol are not qualified for mixed-version operation, and reverse
migrations cannot reconstruct cleared execution configuration or resume fenced
jobs. To return to `rc.8`, restore the coordinated pre-upgrade PostgreSQL and
object-storage backup into a clean environment and deploy the `0.1.0-rc.8` chart.
Prefer correcting migration data or configuration and completing the forward
upgrade.
