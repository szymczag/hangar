## Security and privacy

**The workshop planner no longer crashes on the holds it renders.** The label
helper combined `timeStyle` with individual date fields, which ECMA-402 rejects
with a `TypeError` rather than merging. Every render that had a hold or a
candidate to show threw, leaving coordinators with a dead page; an empty planner
looked correct, which is how this reached `rc.48`. Anyone running `rc.48` with
planning holds in use should take this release.

**Password authentication is rate-limited.** The sign-in and sign-up endpoints
for both the application and the public space now count attempts through
`plane.authentication.rate_limit`, so a caller cannot test credentials at machine
speed against an instance reachable from the internet. The contract tests assert
the refusal rather than the happy path.

**Two API write paths no longer accept fields they never intended to expose.**
Cycle archival and issue-link updates accepted the full serializer payload, so a
caller could set attributes the endpoint was not written to change. Both now
constrain the update to the fields the operation owns. Issue references supplied
through the external API are validated rather than trusted, and a reference that
does not resolve is rejected instead of stored.

**Error responses disclose less.** The instance maintenance and configuration
endpoints returned exception detail to unauthenticated callers on some failure
paths; they now return the failure without the internals. A dependency advisory
affecting the editor's attribute merging is resolved in the same change.

**Production container runtimes are hardened.** The web, admin, API, live, space
and proxy images pin their bases, drop build tooling from the final layer, and
stop running as root where they still did. A test asserts these properties for
every image, so a future Dockerfile edit that reintroduces one fails in CI.

**The Home defaults screen no longer offers two switches with nothing behind
them.** `new_at_plane` and `quick_tutorial` are registered with no component and
are filtered out of the preferences the home endpoint creates, so they could
never appear on anybody's home page. They rendered as raw key names, because
nothing ever intended to display them.

**The all-in-one image builds again.** Its runner stage upgrades `apk-tools`,
then overwrites `/usr/lib` wholesale from the node stage, which put an upgraded
`/sbin/apk` next to an older `libapk.so` and broke every later `apk` call. All
package installation now happens before that copy. This blocked `rc.49` from
publishing at all.

## Migrations and compatibility

This release adds no migrations. No tables, columns or audit actions change, and
the chart adds no Kubernetes resources, Secrets, storage, RBAC, NetworkPolicies,
public routes or configuration values. This was verified against the diff rather
than inferred from commit subjects.

Deploy the application images as one unit. The API changes above tighten what two
write paths accept, so an `rc.48` web against an `rc.49` API is supported, but the
reverse is not: an `rc.49` web may send a payload that an older API still accepts
loosely.

The visual-regression suite is now a required check for every pull request. It
photographs thirty-four surfaces at zero tolerance, refuses any test whose browser
writes to the shared stack, refuses a pull request quietly rewriting more than
three baselines, and soaks itself weekly because a baseline that encodes the day
it was recorded passes on that day and breaks the following morning.

## Known limitations and rollback

Rolling back to `rc.48` restores the workshop planner crash. `rc.49` was
tagged but never published -- its all-in-one image failed to build -- so `rc.48`
is the previous released version. Nothing in this
release writes schema, so there is no data to reverse: a rollback is a matter of
returning every application image to `rc.48` as one unit.

The instance console's second-factor screens remain outside the visual suite.
They are gated on `window.PublicKeyCredential`, which the suite's container does
not expose because it serves over plain HTTP, so a baseline taken today would
photograph the unsupported-browser state rather than the real one.

The evaluation profile remains qualified on AMD64 only. The production profile
remains unsupported, and no new live-cluster qualification has yet been completed
for this release candidate.
