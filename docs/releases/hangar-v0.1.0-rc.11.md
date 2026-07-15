## Security and privacy

`rc.11` makes Epic a canonical level-1 work-item type instead of a separate web
collection. The authenticated application API and public API now share centralized
validation for work-item type and parent assignment. They reject inactive or
unlinked type identifiers, parents outside the target workspace and project, Epic
parents, and direct or indirect hierarchy cycles. Bulk child attachment rejects
duplicate and cross-project identifiers, applies no partial mutation when one item
is invalid, accepts at most 100 children per request, and caps hierarchy depth at
100 levels.

Parent ancestry is evaluated with one bounded, parameterized PostgreSQL recursive
query. Hierarchy mutations serialize against the project and affected work-item
rows, and activity side effects are queued only after the database commit. Raw
relation objects are read-only at serializer boundaries; writes use the validated
identifier fields. These controls make authorization scope and graph integrity
server invariants rather than client assumptions.

The web application uses one Work Items service, MobX state graph, action layer,
and navigation path for Task, Epic, and custom types. Former Epic store names are
compatibility aliases rather than a second cache. This release adds no telemetry,
external destination, Secret, public object-storage route, chart permission, or
network-policy exception.

## Migrations and compatibility

This release applies Django migration `db.0127_issue_type_system_keys`. It adds a
stable nullable `system_key` to work-item types, provisions canonical Task and Epic
types for every active project, makes Task the level-0 project default, places Epic
at level 1, and assigns Task to active work items without a type. A custom type
named `Task` is preserved as custom. The oldest active legacy Epic type is reused
when possible, and no legacy or custom type row is deleted.

The complete schema and data migration is atomic on PostgreSQL. It explicitly
settles deferred foreign-key checks after provisioning and before creating the
partial unique index and system-invariant check constraint. A failure therefore
rolls back the column, provisioned rows, backfill, and constraints together. The
release migration test exercises the real `0126` to `0127` path and asserts that
the migration remains atomic.

Upgrade the API, workers, Live service, frontends, and migration Job as one release,
and prevent old and new versions from accepting concurrent project or work-item
writes during the migration window. Kubernetes 1.30 through 1.36, Helm 4.2,
`linux/amd64`, Restricted Pod Security Admission, TLS ingress with WebSocket
support, a `NetworkPolicy`-enforcing CNI, and persistent storage remain the
qualified boundary. Production support remains unavailable.

## Known limitations and rollback

The former project `/epics` web route redirects to Work Items. The older `/epics`,
`/v2/epics`, and Epic sub-resource APIs remain authenticated, project-scoped
compatibility adapters for existing integrations; new clients should use standard
Work Items endpoints and the type filter. Custom level-1 type hierarchies are not
introduced by this release. The 100-child request limit and 100-level hierarchy
limit are intentional integrity bounds.

Reversing `db.0127` removes the stable identity column and database constraints but
intentionally leaves provisioned Task/Epic rows, project links, and backfilled
work-item type assignments in place. Rolling only the application back to `rc.10`
also restores its separate Epic client behavior. Prefer a forward repair and
redeploy `rc.11`. An exact rollback requires stopping newer Pods, restoring the
pre-upgrade PostgreSQL backup, and deploying the `rc.10` chart and images together
before accepting writes.
