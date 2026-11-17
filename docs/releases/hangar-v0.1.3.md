## Security and privacy

This release brings in the access-control fixes of upstream Plane 1.5.0 that
Hangar did not already carry. Every security fix in upstream 1.4.1 to 1.5.0 was
checked against Hangar; the rest were already fixed here, several of them more
strictly.

**Every live collaboration connection now checks page access.** Hangar checked
access to a page only on the connection that first loaded it, so any signed-in
user could join a page that was already open by its ID. Each connection is now
checked with the connecting user's own session, guests join read-only, and a
title change is saved with the credentials of the user who made it.

**A workspace admin can no longer remove a project's only admin.** The check
that should have refused it compared the wrong ID and never matched. Removing a
member, or demoting them to guest, is now refused while they are the only admin
of a project, and a member update accepts only the role. This completes the
fix for upstream Plane advisory
[GHSA-f739-39g5-jj49](https://github.com/makeplane/plane/security/advisories/GHSA-f739-39g5-jj49).

**Restricted guests can no longer see links and subscribers of hidden work
items.** In a project where guests see only their own work items, a guest could
still list the links of other work items and list, add or remove their
subscribers. Those endpoints now apply the same rule as the work item pages.

**Member lists return only the fields they are meant to.** Endpoints that pass a
field allowlist to their serializer returned every column instead, so a guest
reading the workspace or project member list received each member's full
membership row. Responses now contain only the listed fields.

**Mentions search stays inside the project.** Any workspace member could list
the members of a project they do not belong to through the mention search. It
now answers only active members of that project. A project lead or default
assignee must also be an active member of the workspace.

PyJWT is raised to 2.15.1, and the dependency audit no longer carries an
exception for a PyJWT advisory that does not affect the pinned version.

## Migrations and compatibility

This release adds one database migration, `db.0136`, which creates an index on
the snooze time of intake work items with `CREATE INDEX CONCURRENTLY`. It does
not lock the table and runs outside a transaction. If the build is interrupted
it leaves an invalid index behind; run
`DROP INDEX CONCURRENTLY IF EXISTS intake_issue_snoozed_till_idx;` before
running the migration again. Nothing changes
in the Helm chart, its values or its Secrets. Upgrade from `0.1.2` with the
`0.1.3` `setup.sh` or `swarm.sh`, or with `helm upgrade` on Kubernetes.

**The all-in-one image keeps its generated keys on the data volume.** Earlier
images kept the generated `SECRET_KEY` and `LIVE_SERVER_SECRET_KEY` inside the
container, so recreating it signed everybody out and made saved instance
settings unreadable. They are now kept in `/app/data/secrets.env`; mount a
volume at `/app/data`. The first start of `0.1.3` in an existing container
copies its keys there. Before replacing a `0.1.2` container instead, read its
keys out as the all-in-one README describes.

Behaviour changes for API clients and operators:

- A workspace member update that sends anything but `role` now answers `400`.
  The Hangar web app sends only the role.
- Responses of the member list endpoints contain only their documented fields.
- On the external API (`/api/v1/`) a JSON body that is not an object answers
  `400`, a work item identifier with a non-numeric sequence answers `404`, an
  upload with an unusable `size` answers `400`, and a `POST` to the legacy
  per-file route answers `405`, where each returned `500`. `?expand=` returns
  `null` for an empty relation, and module state counts count work items.
- Live now asks the API about page access on every connection, so the `live` and
  `api` images must come from the same release.
- The web app sends API requests and opens settings pages with a trailing
  slash, which fixes requests failing behind ingresses that do not redirect.
- Snoozed intake work items return at midnight in the project's timezone on the
  chosen day.
- `GUNICORN_WORKERS` and `AUTHENTICATION_RATE_LIMIT` in `plane.env` now take
  effect on Docker Compose; `swarm.sh` accepts its Exit option; host scripts
  find `bash` through `PATH`; the all-in-one image starts with a host directory
  mounted at `/app/logs`.
- The web app no longer reloads in a loop when a session expires, keeps
  sub-work items visible after they load, saves a profile with an empty last
  name, keeps the timeline's scroll position in full screen, and fires the Power
  K copy shortcuts on Windows and Linux. Czech, Polish, Korean and German
  translations are corrected.

Upgrade from `0.1.2`. An upgrade from `0.1.2` to this release, followed by a
restore of its backup into a new installation, is tested as part of the release.

Product version is `v0.1.3`, Git tag `hangar-v0.1.3`, Helm chart version
`0.1.3`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.3`.

## Known limitations and rollback

The Kubernetes production profile has still not completed qualification, so do
not run the chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that does. Hangar is
still based on upstream Plane 1.4.0 with the 1.4.3 changes backported; the
upstream 1.5.0 interface and its other features are not included.

**Rolling back to `0.1.2`** needs no schema change: the index added by
`db.0136` can stay, and `0.1.2` ignores it. Rolling back reopens the access
issues above. An all-in-one container rolled back to `0.1.2` reads its keys
from `/app/plane.env` again, so pass them with `-e` if that container was
created by `0.1.3`.
