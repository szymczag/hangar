## Security and privacy

`rc.10` restores the Epic collection to the same authenticated, paginated issue
contract used by the other project layouts while retaining an Epic-only server
queryset. Filtered and grouped totals are calculated from that scoped queryset,
so a client cannot expand an Epic response to ordinary work items by changing
pagination parameters. Epic creation still forces the project Epic type and
continues to reject client control of parent, draft, archive, and deletion state.

The web client now validates the collection response before mutating its issue
store. A failed request or incompatible response clears the loader and presents a
terminal reload action; an aborted stale request cannot overwrite the state of a
newer request. This prevents an API or deployment mismatch from leaving the Epics
view in an indefinite loading state.

Todoist's conditional uniqueness constraints and importer idempotency protocol
remain unchanged. This release adds no telemetry, external destination, Secret,
public object-storage route, or chart permission.

## Migrations and compatibility

This release applies Django migration
`db.0126_optional_issue_external_identifiers`. It records `None` as the model
default for the nullable `external_source` and `external_id` fields on work items
and comments. The change restores ordinary work-item, Epic, and comment creation,
which `rc.9` serializers incorrectly treated as requiring importer identifiers
after the conditional Todoist uniqueness constraints were added.

The migration does not rewrite existing rows and does not remove or weaken the
partial unique indexes created by `db.0125`. Import-created work items and comments
remain unique within their existing Todoist scopes. Upgrade the API, task workers,
import workers, Beat, and migration Job as one release, then test ordinary
creation, Epic list/group/pagination responses, and a synthetic idempotent import.

Kubernetes 1.30 through 1.36, Helm 4.2, `linux/amd64`, Restricted Pod Security
Admission, TLS ingress with WebSocket support, a `NetworkPolicy`-enforcing CNI,
and persistent storage remain the qualified boundary. Production support remains
unavailable.

## Known limitations and rollback

Todoist schedules that Hangar cannot represent as native dates remain preserved
as import metadata and produce the `unsupported_schedule` diagnostic. Todoist
sections still become modules and enable the Modules project feature. These are
intentional import semantics, not failed rows. Imports remain additive, and
cancellation or retry does not delete project records that were already committed.

An Epic collection failure now requires the operator or user to reload the page
after the underlying API, routing, authorization, or version mismatch is fixed;
the client does not retry an incompatible response automatically.

The `db.0126` database state remains compatible with the `rc.9` column layout,
but returning the application to `rc.9` reintroduces normal-creation failures and
the Epic collection mismatch. Prefer a forward repair and redeploy `rc.10`. If an
emergency rollback is required, preserve the pre-upgrade PostgreSQL backup, keep
the API and workers on one version, do not reverse the migration while newer Pods
are running, and verify both ordinary creation and Todoist idempotency before
resuming imports.
