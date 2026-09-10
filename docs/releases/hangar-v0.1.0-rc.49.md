## Security and privacy

**Password authentication is rate-limited.** The sign-in and sign-up endpoints
for both the application and the public space now count attempts through
`plane.authentication.rate_limit`, so a caller cannot test credentials at
machine speed against an instance that is reachable from the internet. The limit
applies per address, and the contract tests assert the refusal rather than the
happy path.

**Two API write paths no longer accept fields they never intended to expose.**
Cycle archival and issue-link updates accepted the full serializer payload, so a
caller could set attributes the endpoint was not written to change. Both now
constrain the update to the fields the operation owns. Issue references supplied
through the external API are validated rather than trusted, and a reference that
does not resolve is rejected instead of being stored.

**Error responses disclose less.** The instance maintenance and configuration
endpoints returned exception detail to unauthenticated callers in some failure
paths. They now return the failure without the internals. A dependency advisory
affecting the editor's attribute merging is resolved in the same change.

**Production container runtimes are hardened.** The web, admin, API, live, space
and proxy images pin their bases, drop build tooling from the final layer and
stop running as root where they still did. A test asserts the properties hold for
every image, so a future Dockerfile edit that reintroduces one fails in CI.

## Fixes

**The workshop planner no longer crashes on the holds it renders.** The label
helper combined `timeStyle` with individual date fields, which ECMA-402 rejects
with a `TypeError` rather than merging. Every render that had a hold or a
candidate to show threw; an empty planner looked correct, which is how this
reached `rc.48`. Anyone running `rc.48` with planning holds in use should take
this release.

**The Home defaults screen no longer offers two switches with nothing behind
them.** `new_at_plane` and `quick_tutorial` are registered with no component and
are filtered out of the preferences the home endpoint creates, so they could
never appear on anybody's home page. They rendered as raw key names, because
nothing ever intended to display them.

## Testing and release engineering

The visual-regression suite is now a required check. It photographs thirty-four
surfaces at zero tolerance and has caught two defects that no unit test could:
a wordmark rendered inside a square badge, and a logo that never painted. This
release adds the import history, pending invitations and duplicate-project
surfaces; a guard that fails any test whose browser writes to the shared stack;
a guard that refuses a pull request quietly rewriting more than three baselines;
and a weekly soak, because a baseline that encodes the day it was recorded passes
on that day and breaks the following morning.

Release and preview CI paths are shortened by scoping checks to the packages a
change touches and by qualifying the chart and AIO images in parallel.

## Migrations and compatibility

**No migrations.** This release adds no tables, columns or audit actions, and no
chart resources, Secrets, storage, RBAC, NetworkPolicies, public routes or
configuration values change.

Application images should still be deployed as one unit. The API changes above
tighten what two write paths accept, so a `rc.48` web against an `rc.49` API is
supported, but the reverse is not: an `rc.49` web may send a payload that an
older API still accepts loosely.

## Known limitations and rollback

Rolling back to `rc.48` restores the workshop planner crash. There is no data to
reverse — nothing in this release writes schema — so a rollback is a matter of
returning every application image to `rc.48` as one unit.

The instance console's second-factor screens remain outside the visual suite.
They are gated on `window.PublicKeyCredential`, which the suite's container does
not expose because it serves over plain HTTP, and a baseline taken today would
photograph the unsupported-browser state rather than the real one.

The evaluation profile remains qualified on AMD64 only. The production profile
remains unsupported, and no new live-cluster qualification has yet been completed
for this release candidate.
