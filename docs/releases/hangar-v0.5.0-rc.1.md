## Security and privacy

**The active cycles page no longer links off the instance.** Up to and
including `0.4.0`, the workspace's Active cycles page showed an "Upgrade"
button that opened the address behind upstream's pricing link, which Hangar
points at its README on GitHub (or at `VITE_DOCUMENTATION_URL`), in a new tab.
Unlike every other outbound link in the web app, it showed whether or not the
instance allows external links (`INSTANCE_SHOW_EXTERNAL_LINKS`, off by
default), so the `0.4.0` notes' "every outbound link renders only where the
instance allows external links" did not hold on that page. The button is gone;
Hangar has no paid tier to point at. The page keeps its feature description.

**The new design brings in none of upstream's external services, and guests
still see no worklogs.** The work item and other screens that move to Propel in
this release, described below, are upstream Plane `1.5.0`'s, merged with
Hangar's changes:

- Guests still never see time tracking. The work item detail page and the peek
  now render their properties from one upstream component, which had no place
  for Hangar's rows; Hangar's slot is restored at the end of its "Details"
  group. The time tracking row, the worklog entries in the activity feed and
  the worklog filter show only to someone whose project role may read
  worklogs, and "Log time" only to project admins and the work item's
  assignees, never on intake. The server's own checks are unchanged and stay
  authoritative. No list layout, column or property shows worklog data.
- Upstream's bulk operations "Upgrade to One" banner is not taken. Hangar has
  no bulk operations, so the banner never showed, and it is removed.
- Every link the moved screens open in a new tab stays on the instance: a work
  item, an attachment's own file, a project's or view's published board on
  this instance's Spaces. No screen loads an image from another host.
- The page export is still rendered by this instance's live server from the
  saved page, in the same formats (PDF and Markdown) and page sizes; no
  third-party service and no PDF library in the browser. The page icon picker
  reads the emoji data this instance serves.
- Upstream's tracking attributes and capture calls are not taken. The web app
  adds no inline script or style, no `innerHTML` and no exception to its
  Content-Security-Policy, and the editor keeps Hangar's Trusted Types policies
  and sanitisation; the reviewed inventory of script sinks is unchanged.
- Permissions on the moved screens are unchanged: intake accept, decline and
  duplicate for project admins and members, intake delete for admins or the
  work item's creator, cycle and module edits for admins and members, and only
  project admins create a label from the create dialog. Mentions keep their
  stored ids.

## Migrations and compatibility

**The web app's work items, cycles, modules, views, pages, analytics and
intake move to the new upstream 1.5.0 design.** These screens now use the
Propel and `@plane/blocks` components from upstream Plane `v1.5.0`, merged
with Hangar's changes, as the shell, sign-in, projects and settings did in
`0.4.0`:

- The work item detail page and the peek. State, priority, assignees and dates
  move from the sidebar into a row under the title, and the sub-work item,
  relation, link and attachment buttons become one toolbar. The activity gets
  All, Activity and Comments tabs, with "Log time", the filter and the sort
  beside them. The properties sidebar is grouped into a collapsible "Details"
  group (parent, labels, time tracking and the work item type's custom
  properties) and "Project structure" (cycle, modules), with the created and
  updated dates at the foot.
- The list, board, spreadsheet, calendar and gantt layouts, their quick add,
  row properties, quick action menus and headers. Properties that do not fit a
  row collapse into a "+N" menu, and the display menu is a menu with "Group
  by" and "Order by" submenus. The filters menu is upstream's, with a search
  field. Hangar's parent property, parent spreadsheet column and parent and
  Epic groupings stay. At narrow widths the list puts a row's properties on a
  second line, as upstream does.
- The work item create and edit dialog, workspace drafts, and the project and
  workspace saved views with their dialogs. The work item type stays first in
  the dialog's property row. Discarding a draft still saves it with its
  property values.
- Pages: the list, its filters, the editor's toolbar, the navigation pane with
  the version history panel, and the export dialog. Stickies.
- Cycles (list, page, analytics sidebar, active cycle, archive), modules (list,
  page, analytics sidebar, links, archive), workspace analytics, whose figures
  are unchanged, and intake (list, detail, create, snooze, decline and
  duplicate dialogs). The filters of the cycle, module, intake, page and view
  lists become upstream's menus, with submenus such as status, created date and
  created by in place of the old list of every option under a search box.
- Hangar's own settings pages: home defaults, Todoist import history, workshop
  checklists, and the encrypted e-mail and receipts sections of account
  security, with the notice on the notifications page. They keep their
  requests and rules. Deleting a workshop template or role now asks in a dialog
  instead of the browser's confirmation box, with the same text.

Epics stay a work item type. Reload open web app tabs after the upgrade. What
still keeps the Plane 1.4 components is listed under
[Known limitations](#known-limitations-and-rollback).

**Choosing "No estimate" now clears the estimate.** Up to and including
`0.4.0`, choosing "No estimate" left an estimate that was already
set: the web app sent the change without the estimate field, so the server
kept the old value. It now sends an empty estimate from the detail page, the
peek, every list layout, the create and edit dialog, workspace drafts and the
intake create dialog.

**The create dialog shows a work item type's custom properties again.** Since
the Plane 1.4.0 sync, the work item create dialog had stopped showing the
custom properties of the chosen work item type, but still required the ones
marked as required. A work item of a type with a required property could not
be created from the dialog, and the dialog did not say why. The properties now
appear under the description. Their inputs, shared with the detail sidebar,
move to the new components on both.

**Light mode and wording fixes from the `0.4.0` test rounds.** In light mode,
the General page of a project's settings now shows the name of a project
without a cover image readably; it was white on near-white. The Hangar logo,
drawn for a dark surface, now turns dark outside the dark theme on the
sign-in, sign-up, password, onboarding, invitation and create-workspace pages,
the God Mode sign-in page, the Spaces sign-in, signed-in and failure pages,
and the other light surfaces that show it. The set-password page now has its
own title instead of the sign-in header with "New to Hangar? Sign up". The
dialogs that show a new API token's secret, a webhook's secret and an
application's client secret once no longer tell you to save the secret "in
Hangar Pages"; they tell you to store it somewhere safe, in all 19 languages.
The lite editor's attach button has its label again.

**The API no longer logs a server error for every 404.** The shared view base
of the application API printed a bare `Server Error` line to standard output
(with the exception and traceback under `DEBUG`) for every exception it left
to the framework, before it chose the status. Every request for a missing
object therefore left a server-error line in the `api` log. The print is gone.
Real server errors are still logged through the `plane.exception` logger, as
before.

**No migration and no chart change.** This release adds no database or license
migration compared with `0.4.0`, and the migrations lockfile is unchanged. The
Helm chart's templates, values and Secrets do not change. The Compose and
Swarm deployment contract does not change either: `variables.env` is the same,
and the published `docker-compose.yml` keeps its services, settings and
variables. The file itself does change, as it does in every release: its header
names `v0.5.0-rc.1`, and it pins the Hangar images to this release's digests.
Each release builds all seven Hangar images (`web`, `admin`, `space`, `live`,
`api`, `proxy` and the all-in-one `aio`) afresh, with the release's version and
refreshed Alpine packages, so every image digest changes. Of the application
code, `web` carries the changes described here; `api` changes only in the
404 logging (the Celery workers, the scheduler and the migrator run the `api`
image); `admin` and `space` change only in the logo on light surfaces; and the
all-in-one image bundles them all. The `live` and `proxy` code is unchanged.
`setup.sh` and `swarm.sh` are unchanged since `0.4.0`, apart from the release
each names (`SCRIPT_RELEASE`), which the release workflow writes into them.

Upgrade from `0.4.0`. This is a release candidate, so the installers do not
pick it on their own, and the `0.4.0` script refuses a newer release than its
own. On Compose and Swarm:

1. Let the script replace itself:
   `HANGAR_RELEASE=v0.5.0-rc.1 ./setup.sh update-script`. It downloads and
   verifies the new script and changes nothing if a check fails. It checks the
   Cosign signature of `SHA256SUMS` only when `cosign` is installed; without
   it, it prints a `WARNING` and compares the script only with the
   `SHA256SUMS` downloaded beside it. Add `HANGAR_REQUIRE_SIGNATURE=1` to make
   the signature check mandatory: without Cosign the command then refuses and
   leaves the old script in place.
2. On Compose, back up before you upgrade: run `./setup.sh backup` while the
   services are running and keep `plane-app/plane.env` with it
   (`install -m 600 plane-app/plane.env plane-app/backup/<folder>/plane.env`).
   The upgrade takes no backup itself. Be aware that `setup.sh backup` copies
   the running database's data directory rather than dumping it, so the copy is
   not guaranteed to be consistent: take it while nobody uses the instance, and
   keep a `pg_dump` beside it as
   [Backup Data](../../deployments/cli/community/README.md#backup-data-docker-compose)
   shows. Swarm has no backup action; back up the volumes on the node that
   holds them.
3. Run `HANGAR_RELEASE=v0.5.0-rc.1 ./setup.sh upgrade`, as the owner of
   `plane-app/` or as root.
4. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES` and the command that starts them:
   check `plane-app/plane.env`, then run `./setup.sh start`. Hangar stays down
   until you do. On Swarm, the upgrade redeploys the stack itself.
5. For later releases, run `HANGAR_RELEASE=<release> ./setup.sh update-script`
   (or plain `./setup.sh update-script` for the latest stable release) before
   `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells you what
   to run.

Use the `v0.5.0-rc.1` all-in-one image, or run `helm upgrade` with
`--version 0.5.0-rc.1` on Kubernetes. Neither needs a further step. Reload
open web app tabs after the upgrade. Upgrading from a release older than
`0.4.0`, including a `0.4.0` release candidate, also brings what the
[`0.4.0` notes](hangar-v0.4.0.md) and the releases before it describe; read
them first. In particular, the `0.3.0` script cannot replace itself and must be
replaced by hand as those notes show, and their steps for the invitation switch
and the worker logs apply.

Product version is `v0.5.0-rc.1`, Git tag `hangar-v0.5.0-rc.1`, Helm chart
version `0.5.0-rc.1`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.5.0-rc.1`.

## Known limitations and rollback

This is the first release candidate for `0.5.0`. `0.4.0` stays the current
stable release, and the installers keep choosing it unless you name this
release.

God Mode, the published boards and most of the web app now have the new
design. The notifications, the profile pages and Hangar's capacity and
workshop screens, including the workshop schedule and sessions on a work item,
keep their Plane 1.4 components until they move in later releases. The web
app's `custom` theme gets the light treatment of the Hangar logo, which may not
suit a dark custom palette. The recorded upstream base stays Plane 1.4.0 with
the 1.4.3 changes backported.

- Invitations sent before `0.4.0` have no recorded sender and stay with
  admins, as the `0.4.0` notes describe.
- Page history starts with the upgrade to `0.4.0` (or `0.4.0-rc.2`); edits
  made before that have no versions.
- A mention keeps the mentioned user's id in the stored text of a description
  or comment, so a visitor of a published board can tell that some account was
  mentioned, but nothing on the board turns the id into a name.
- On Kubernetes this release is qualified for evaluation on AMD64 only: the
  production profile has still not completed qualification, so do not run the
  chart in production yet.

The all-in-one image does not send `Strict-Transport-Security` itself; put it
behind a proxy that adds it if you need it.

**Rolling back to `0.4.0`** needs no schema change and no change to the Helm
values: only the images change. Work items, views, drafts, pages and stickies
created on this release stay readable there. Rolling back brings back the
"Upgrade" button on the active cycles page that links off the instance
regardless of the external links switch, "No estimate" that does not clear an
estimate, the create dialog without custom properties, the light-mode contrast
faults and the old secret dialog wording, the `Server Error` line for every
404 in the `api` log, and the Plane 1.4 components on the screens that move
here. The release check in this release's script never refuses an older
release, so it does not stand in the way of a rollback.
