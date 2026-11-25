## Security and privacy

**Guests no longer see logged time in activity outside the work item.**
Logging time on a work item writes an activity entry whose value is the logged
duration. Worklogs are for project admins and members and for workspace admins
only: the worklog endpoints and the work item's own activity feed already kept
them from project guests. Up to and including `0.4.0`, and in every Hangar
release since worklogs arrived in `0.1.0`, four other surfaces that list
activity of every kind returned the worklog entries to guests, duration
included:

- a user's profile activity feed
  (`/api/workspaces/<slug>/user-activity/<user_id>/`);
- its CSV export, "Download today's activity";
- the public API's activity list and detail of a work item
  (`/api/v1/…/issues/<id>/activities/` and `…/activities/<pk>/`), for an API
  token of a guest;
- the notifications sent to a work item's subscribers, in the app and by
  e-mail, for a subscriber who is a guest of the project, and the stored ones,
  including those a member received before being demoted to guest.

The gap is Hangar's own: upstream Plane has no worklogs. The four surfaces now
apply the rule the worklog endpoints use. The profile feed, its export and both
public API endpoints leave out a worklog entry unless the reader is an admin or
member of its project, or a workspace admin. The notification task no longer
sends a worklog entry, in the app or by e-mail, to a subscriber who may not read
the project's worklogs; the other entries in the same change still notify. The
notification endpoints check the receiver's current role whenever a
notification is read, so a guest no longer lists, counts, opens, snoozes,
archives or marks a worklog notification stored before the upgrade or before
their demotion. The web app's profile feeds and inbox hide a worklog entry for
a reader whose project role may not read worklogs, including one the browser
already holds. Every other kind of activity is unchanged, and so are the work
item's own feed and the worklog endpoints.

One residual remains: e-mails already queued in the e-mail log when the upgrade
is deployed are sent by the mailer as they were written, without checking the
receiver's role again. The mailer sends in batches every few minutes, so only
the e-mails waiting at that moment are affected.

**The active cycles page no longer links off the instance.** Up to and
including `0.4.0`, the workspace's Active cycles page showed an "Upgrade"
button that opened the address behind upstream's pricing link, which Hangar
points at its README on GitHub (or at `VITE_DOCUMENTATION_URL`), in a new tab.
Unlike every other outbound link in the web app, it showed whether or not the
instance allows external links (`INSTANCE_SHOW_EXTERNAL_LINKS`, off by
default), so the `0.4.0` notes' "every outbound link renders only where the
instance allows external links" did not hold on that page. The button is gone;
Hangar has no paid tier to point at. The page keeps its feature description.

**The new design brings in none of upstream's external services, and keeps
worklogs from guests.** The work item and other screens that move to Propel in
this release, described below, are upstream Plane `1.5.0`'s, merged with
Hangar's changes:

- Guests still never see time tracking on a work item. The work item detail
  page and the peek now render their properties from one upstream component,
  which had no place for Hangar's rows; Hangar's slot is restored at the end of
  its "Details" group. The time tracking row, the worklog entries in the
  activity feed and the worklog filter show only to someone whose project role
  may read worklogs, and "Log time" only to project admins and the work item's
  assignees, never on intake. The server's own checks stay authoritative. No
  list layout, column or property shows worklog data.
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

**Creating an intake item on a project without intake no longer leaves a
stray work item.** Up to and including `0.4.0`, and in upstream Plane, the
application's intake endpoint
(`/api/workspaces/<slug>/projects/<id>/intake-issues/`) saved the work item
before it looked up the project's intake. On a project whose intake was never
turned on, the lookup then failed: the request answered `500`, and the work
item stayed behind in the project's work item list, outside intake. On a
project whose intake had been turned off again, the item was accepted into
intake. The web app hides intake while it is off, so only direct requests to
the API reached either case. Creating an intake item now refuses with `400`
(`Intake is not enabled for this project`) when the project has no intake or
it is turned off, and writes nothing. The work item and its intake entry are
saved together, so a later failure leaves neither behind. Reading an intake
item on a project that never had intake answers `404` instead of `500`, and
updating or deleting one answers `404` with the same `Intake not found` error.
Existing intake items can still be read, triaged and deleted in the app after
intake is turned off, as before.

**Behaviour change for clients of the API-token API: intake writes need intake
turned on.** In the public API (`/api/v1/`), creating, updating and deleting an
intake item used to be refused only when the project had no intake and intake
was turned off. A project with intake turned off but an intake from earlier
still accepted all three, and a project with intake turned on but none created
answered `500` and kept the new work item. All three are now refused with `400`
and the same error as before (`Intake is not enabled for this project enable it
through the project's api`) whenever the project's intake is turned off or
missing, as the list and detail reads already were. **A script or integration
that updates or deletes intake items through `/api/v1/` while the project's
intake is turned off now receives `400`**: turn intake on for the project first,
or make the change in the app, which still allows it. No other `/api/v1/`
endpoint changes, apart from the worklog entries left out of the activity list
for guests, as described [above](#security-and-privacy).

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
worklog and intake fixes only filter, refuse or reorder requests; they change
no table and need no data step. The Helm chart's templates, values and Secrets
do not change. The Compose and Swarm deployment contract does not change
either: `variables.env` is the same, and the published `docker-compose.yml`
keeps its services, settings and variables. The file itself does change, as it
does in every release: its header names `v0.5.0`, and it pins the Hangar images
to this release's digests. Each release builds all seven Hangar images (`web`,
`admin`, `space`, `live`, `api`, `proxy` and the all-in-one `aio`) afresh, with
the release's version and refreshed Alpine packages, so every image digest
changes. Of the application code, `web` carries the design move and the other
web app changes described here, and the worklog gate on the profile feeds and
inbox; `api` carries the worklog fix, the intake fix and the 404 logging (the
Celery workers, which send the notifications, the scheduler and the migrator
run the `api` image); `admin` and `space` change only in the logo on light
surfaces; and the all-in-one image bundles them all. The `live` and `proxy`
code is unchanged. `setup.sh` and `swarm.sh` are unchanged since `0.4.0`, apart
from the release each names (`SCRIPT_RELEASE`), which the release workflow
writes into them. The in-app release notes in the web app name this release.

Upgrade from `0.4.0`. The installers pick `0.5.0` on their own as the latest
stable release, but the `0.4.0` script refuses a newer release than its own,
so on Compose and Swarm:

1. Let the script replace itself: `./setup.sh update-script`. It downloads the
   script of the latest stable release, `0.5.0`, verifies it and changes
   nothing if a check fails. It checks the Cosign signature of `SHA256SUMS`
   only when `cosign` is installed; without it, it prints a `WARNING` and
   compares the script only with the `SHA256SUMS` downloaded beside it. Add
   `HANGAR_REQUIRE_SIGNATURE=1` to make the signature check mandatory: without
   Cosign the command then refuses and leaves the old script in place.
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
3. Run `./setup.sh upgrade`, as the owner of `plane-app/` or as root. It picks
   `0.5.0`, the latest stable release.
4. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES` and the command that starts them:
   check `plane-app/plane.env`, then run `./setup.sh start`. Hangar stays down
   until you do. On Swarm, the upgrade redeploys the stack itself.
5. For later releases, run `./setup.sh update-script` (or
   `HANGAR_RELEASE=<release> ./setup.sh update-script` for a named release)
   before `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells
   you what to run.

Use the `v0.5.0` all-in-one image, which the `stable` tag now also points to,
or run `helm upgrade` with `--version 0.5.0` on Kubernetes. Neither needs a
further step. Reload open web app tabs after the upgrade. If your API clients
change intake items through `/api/v1/`, check the behaviour change above first.
Upgrading from a release older than `0.4.0`, including a `0.4.0` release
candidate, also brings what the [`0.4.0` notes](hangar-v0.4.0.md) and the
releases before it describe; read them first. In particular, the `0.3.0` script
cannot replace itself and must be replaced by hand as those notes show, and
their steps for the invitation switch and the worker logs apply.

**If you run `0.5.0-rc.1`.** `0.5.0` is built from the `0.5.0-rc.1` source
plus the worklog fix, the intake fix and its release notes and version. The
upgrade from `0.5.0-rc.1` follows the same steps: the `0.5.0-rc.1` script also
refuses `0.5.0` as a newer release, so on Compose and Swarm run
`./setup.sh update-script`, back up, run `./setup.sh upgrade`, then on Compose
`./setup.sh start`. There is no migration and no chart change; only the images
change. On Kubernetes, run `helm upgrade` with `--version 0.5.0`.

Product version is `v0.5.0`, Git tag `hangar-v0.5.0`, Helm chart version
`0.5.0`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.5.0`.

## Known limitations and rollback

`0.5.0-rc.1` was the release candidate for this release and is superseded by
it; do not install it, and upgrade an installation on it to `0.5.0`. The
previous stable release, for upgrades and rollback, is `0.4.0`. The release
pipeline qualifies the Compose upgrade from `0.4.0` before it publishes this
release: `0.4.0` is installed from its release assets, filled with data, backed
up, upgraded with this release's script, and the backup is restored into a
fresh installation.

God Mode, the published boards and most of the web app now have the new
design. The notifications, the profile pages and Hangar's capacity and
workshop screens, including the workshop schedule and sessions on a work item,
keep their Plane 1.4 components until they move in later releases. The web
app's `custom` theme gets the light treatment of the Hangar logo, which may not
suit a dark custom palette. The recorded upstream base stays Plane 1.4.0 with
the 1.4.3 changes backported.

- Worklog e-mails already queued when the upgrade is deployed are sent without
  a new role check, as described above.
- A workspace admin who is a guest of a project may read that project's
  worklogs, and the server shows them the worklog entries. The web app's
  profile feeds and inbox decide from the project role alone, so they can hide
  such an entry from that admin; they never show one the server would refuse.
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

The "No estimate" fault and the two light-mode contrast faults that the `0.4.0`
notes list as limitations are fixed in this release. The all-in-one image does
not send `Strict-Transport-Security` itself; put it behind a proxy that adds it
if you need it.

**Rolling back to `0.4.0`** needs no schema change and no change to the Helm
values: only the images change. An all-in-one installation that follows the
`stable` tag has to name `v0.4.0` to roll back, because `stable` now points to
`0.5.0`. Work items, views, drafts, pages and stickies created on this release
stay readable there. Rolling back brings back:

- worklog entries, with their durations, for guests: in the profile feed and
  its export, in the public API's activity list and detail, and in their
  notifications, including the worklog notifications they received before
  this release or while they were still members;
- the intake endpoint that answers `500` and leaves a stray work item on a
  project without intake, and the public API that accepts intake writes while
  intake is turned off;
- the "Upgrade" button on the active cycles page that links off the instance
  regardless of the external links switch;
- "No estimate" that does not clear an estimate, and the create dialog without
  custom properties;
- the light-mode contrast faults and the old secret dialog wording, and the
  `Server Error` line for every 404 in the `api` log;
- the Plane 1.4 components on the screens that move here.

The release check in this release's script never refuses an older release, so
it does not stand in the way of a rollback. Rolling back to `0.5.0-rc.1` is not
supported, because it is superseded.
