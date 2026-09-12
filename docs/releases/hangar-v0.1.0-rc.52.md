## Security and privacy

**Three advisories are closed, and the instance no longer carries any open
dependency alert.** `sharp` moves to 0.35.4 for a high-severity pair of libheif
vulnerabilities reachable through image handling. `vitest` moves to 4.1.11 for a
path traversal in `@vitest/mocker` that allowed arbitrary file reads through its
redirect handling. `morgan` moves to 1.12.0: below that it writes request fields
into the log without escaping the Unicode line separators U+2028 and U+2029,
which most log viewers treat as line breaks, so a crafted URL or header could
forge entries that read as genuine log lines. The last of those had no automated
update available -- its version is fixed by a workspace override rather than by
any package's own dependencies, which is outside what the dependency bot edits,
so the alert would have stayed open indefinitely.

**Work-item arrays no longer depend on the database happening to sort them.**
The assignee, label and module lists attached to work items, and the vote and
reaction lists on public boards, were built by aggregates that promise nothing
about the order of what they return. Nothing misbehaved -- PostgreSQL satisfies
the deduplication by sorting, so the arrays did arrive sorted -- but that is a
property of the query planner rather than a guarantee, and these arrays are sent
straight to the browser. All fifty-five of them now state the order they want.

## Migrations and compatibility

**Object storage now comes from quay.io, and this matters for self-hosting.** The
`minio/minio` repository has been removed from Docker Hub: it answers "object not
found", and every pull of it fails. `docker-compose.yml` and the community
deployment both named it, so a fresh self-host on `rc.51` or earlier cannot start
object storage at all. Both now name `quay.io/minio/minio` at a pinned tag, which
resolves to the same image the previous floating reference did -- the pull is
fixed without the image underneath anyone changing. An existing deployment whose
image is already pulled keeps running; the break appears on a fresh pull.

This release adds no migrations, changes no API contract, and touches no chart
resources, Secrets, storage, RBAC, NetworkPolicies, public routes or
configuration values.

The capacity pages keep their addresses. `/capacity/team` and `/capacity/planner`
now read the selected week from a `week` query parameter; a link without one
opens on the current week, so existing bookmarks resolve exactly as before.

## Known limitations and rollback

Rolling back to `rc.51` restores the `minio/minio` reference that can no longer
be pulled, so a rollback that is followed by a fresh image pull will fail to
start object storage. A rollback on a host that already holds the image is
unaffected. Nothing here writes schema, so rolling back is otherwise a matter of
returning the images to `rc.51`.

Two limitations recorded against `rc.51` are resolved. The team ledger no longer
overflows its container at 1440 wide, and week selection now carries between
`/capacity/team` and `/capacity/planner` -- the planner can also change the week,
which it previously could not do at all.

The peek panel's workshop-session baseline compares exactly, with no pixel
tolerance, and varies between runs on some local machines through antialiasing on
rounded corners alone. It has been stable in continuous integration, where
rendering is deterministic, but a local suite run may report it as failing when
nothing has changed.

The instance console's second-factor screens remain outside the visual suite.
They are gated on a browser API that requires a secure context, which the suite's
stack does not serve.

The evaluation profile remains qualified on AMD64 only. The production profile
remains unsupported, and no new live-cluster qualification has yet been completed
for this release candidate.
