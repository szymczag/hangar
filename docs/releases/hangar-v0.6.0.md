## Security and privacy

**The visual test seed command no longer runs without an explicit opt-in.**
The `api` image carries `seed_visual_fixtures`, the management command that
fills the disposable stack Hangar's screenshot tests run against. It creates
users with the fixed password `visual-regression` and signs them in. Up to and
including `0.5.0`, nothing stopped it from running against a real database, so
running it there by mistake would have left accounts with a known password on
the instance. It now refuses with an error, before it writes anything, unless
`HANGAR_VISUAL_FIXTURES=1` is set. Only the test stack sets that variable; it
is not in `variables.env`, `setup.sh`, the Helm chart or any production
Compose file, and any other value, such as `true` or `yes`, is refused too.
No installation step uses the command.

**The editor's Markdown serializer no longer writes a callout's logo
unchecked.** A callout stores its logo as page content that anyone who may
edit the page controls: the emoji's code points (`data-emoji-unicode`) or an
icon name (`data-icon-name`). The editor's Markdown serializer, which the web
app, Spaces and the live server all load, wrote both into its output without
escaping, and read code points in any number form. A crafted value could put a
link, an image from another host or raw HTML into the Markdown. The emoji is
now written only when every part is a plain decimal code point and together
they form exactly one emoji (skin tones, families, keycaps and flags still
pass), and the icon name only when it is letters, digits, `-` and `_`;
anything else leaves the logo line out. The serializer still writes the emoji
character, never the image URL the picker stores. A page's Markdown export
and its "Copy markdown" action use a separate converter that does not write
the callout logo, and are unchanged.

**The web app no longer carries upstream's upsell and product-update
screens.** `0.5.0` removed the "Upgrade" button from the workspace's Active
cycles page, which kept its feature description. That page, at
`/<workspace>/active-cycles/`, advertised a paid upstream feature and offered
nothing that worked in Hangar; it is now removed with its images, and the
address no longer leads to a page. Nothing in the app linked to it. Cycles
in each project, and the API, are unchanged. Two pieces of upstream code that
the web app no longer showed are removed as well: the "What's new" dialog,
which framed upstream's changelog website and which Hangar's help menu had
already dropped, and upstream's paid plan, checkout and talk-to-sales cards.
Hangar's own build identity dialog stays.

**The rest of the new design brings in none of upstream's external services,
and keeps worklogs from guests.** The screens that move to Propel in this
release, described below, are upstream Plane `1.5.0`'s where upstream has them,
merged with Hangar's changes, or Hangar's own screens rebuilt on the same
components:

- The profile activity feeds and the notifications inbox keep the worklog gate
  that `0.5.0` added: a worklog entry shows only to a reader whose project role
  may read worklogs. The server's own checks stay authoritative and are
  unchanged.
- The Todoist import wizard still opens no outside address, stays with
  workspace admins behind the instance's Todoist import switch, and never
  displays the preview token it sends back on import.
- The build identity dialog keeps its two links: the source code offer, which
  the AGPL requires, always, and the documentation only where the instance
  allows external links (`INSTANCE_SHOW_EXTERNAL_LINKS`). The production error
  page keeps Hangar's wording and links rather than upstream's support e-mail,
  status page and error-tracking notice.
- Every emoji picker in the web app and in Spaces, including the editor's
  callout logo picker, reads the emoji data this instance serves.
- Upstream's tracking attributes and capture calls are not taken. The web app
  adds no inline script or style, no `innerHTML` and no exception to its
  Content-Security-Policy, and the reviewed inventory of script sinks is
  unchanged. The web app drops four of its old UI dependencies, and the
  lockfile only loses entries: no package is added or upgraded.
- Permissions on the moved screens are unchanged: managing work item types and
  custom properties, the calendar import and the Todoist import stay with
  admins, and who may download profile activity, see the profile tabs, or
  manage home widgets and quick links is as before.

## Migrations and compatibility

**The whole web app now uses the new upstream 1.5.0 design.** The screens that
`0.5.0` left on the Plane 1.4 components move to the Propel and
`@plane/blocks` components from upstream Plane `v1.5.0`, and the web app no
longer loads the 1.4 component libraries at all:

- A user's profile: the overview, with its statistics as cards, and the
  activity feed, which loads more entries on request.
- The notifications inbox, with the All and Mentions tabs beside the filters,
  and upstream's custom snooze dialog.
- The home page: recents, quick links and the manage widgets dialog. The
  quick links a workspace admin shares now look like your own quick links and
  stay above them. Their menu opens a link in a new tab or hides it, or shows
  it again; it does not edit the link. Hidden links still show faded behind
  "Show hidden".
- Hangar's capacity screens: the personal page, the schedule editor, the team
  ledger, the planner with its "Save changes before switching plans?" and
  "Schedule workshop" dialogs, the report and the calendar import.
- Work item types: their settings page, their custom property inputs on the
  work item and in the create dialog, and the type mark next to a work item's
  identifier.
- Workshop sessions and the workshop schedule on a work item, with an icon for
  each kind of time field. Propel has no car icon, so travel time shows a map
  pin.
- The Todoist import wizard, the project copy progress strip and the build
  identity dialog.
- The remaining upstream screens: the set-password notices, the project
  archives, the error pages, the theme switcher, the create workspace page,
  the billing card, the OIDC and SAML sign-in buttons, the instance-not-ready
  page and the quick action menus.
- The maintenance bar and the edition badge in the sidebar. The bar keeps its
  height, so nothing under it moves, and its behaviour: it still checks for a
  notice every minute, remembers the last notice while the API is unreachable,
  stays dismissed for the same notice, and is announced politely to screen
  readers whatever its severity.

Their requests, rules and permissions stay the same. Reload open web app tabs
after the upgrade.

**Clicking a callout's logo opens its picker.** In the web app's editor,
clicking a callout's logo left the logo picker closed. The editor now uses
upstream `1.5.0`'s callout logo picker, the same `@plane/blocks` picker the
rest of the app uses, in the web app and in Spaces; it opens and reads the
instance's emoji data.

**Profile activity now says what a worklog entry did.** A user's profile
activity feed printed a worklog entry as a bare name and time, such as "olga 1
minute ago", because the profile had no wording for it. It now reads like the
work item's own feed, "logged 45m", "updated logged time from 30m to 45m" or
"removed logged time 45m", with the time tracking icon and the work item it
belongs to. Who may see the entry is unchanged.

**Sub-work items can be filtered by work item type.** The filters menu of a
work item's sub-work items gains a "Work item Type" row, which lists the active
types of the parent's project, can be searched, and shows how many are
applied.

**The live server's image build now proves the image can start.** The new
picker components need React, and the `live` image installs only production
dependencies, without it. The first candidate for this release,
`v0.6.0-rc.1`, shipped a `live` image that stopped at startup with
`ERR_MODULE_NOT_FOUND`, because the editor code the server loads reached those
components. The live server now loads only the editor's server-side parts,
and the callout emoji is converted inside the editor, so the server no longer
reaches them. The `live` image build now resolves every import the built
server reaches in its production-only install and stops if one does not
resolve, instead of producing an image that cannot start; pull-request CI runs
the same check without Docker. The check runs in a build stage and adds
nothing to the runtime image. The live server's behaviour is the same as in
`0.5.0`: collaboration, the PDF export and the realtime events are
unchanged.

**No migration and no chart change.** This release adds no database or license
migration compared with `0.5.0`, and the migrations lockfile is unchanged. The
Helm chart's templates, values and Secrets do not change. The Compose and
Swarm deployment contract does not change either: `variables.env` is the same,
and the published `docker-compose.yml` keeps its services, settings and
variables. The file itself does change, as it does in every release: its header
names `v0.6.0`, and it pins the Hangar images to this release's digests.
Each release builds all seven Hangar images (`web`, `admin`, `space`, `live`,
`api`, `proxy` and the all-in-one `aio`) afresh, with the release's version and
refreshed Alpine packages, so every image digest changes. Of the application
code, `web` carries the changes described here; `space` changes only in the
editor's callout logo picker and the callout check of its Markdown serializer;
`live` changes only in which parts of the editor it loads and in that callout
check; `api` changes only in the seed command's guard (the Celery workers, the
scheduler and the migrator run the `api` image); and the all-in-one image bundles them all. The `admin`
and `proxy` code is unchanged. `setup.sh` and `swarm.sh` are unchanged since
`0.5.0`, apart from the release each names (`SCRIPT_RELEASE`), which the
release workflow writes into them. The in-app release notes in the web app name
this release.

Upgrade from `0.5.0`. The installers pick `0.6.0` on their own as the latest
stable release, but the `0.5.0` script refuses a newer release than its own,
so on Compose and Swarm:

1. Let the script replace itself: `./setup.sh update-script`. It downloads the
   script of the latest stable release, `0.6.0`, verifies it and changes
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
   `0.6.0`, the latest stable release.
4. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES` and the command that starts them:
   check `plane-app/plane.env`, then run `./setup.sh start`. Hangar stays down
   until you do. On Swarm, the upgrade redeploys the stack itself.
5. For later releases, run `./setup.sh update-script` (or
   `HANGAR_RELEASE=<release> ./setup.sh update-script` for a named release)
   before `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells
   you what to run.

Use the `v0.6.0` all-in-one image, which the `stable` tag now also points to,
or run `helm upgrade` with `--version 0.6.0` on Kubernetes. Neither needs a
further step. Reload open web app tabs after the upgrade. Upgrading from a
release older than `0.5.0`, including `0.5.0-rc.1`, also brings what the
[`0.5.0` notes](hangar-v0.5.0.md) and the releases before it describe; read
them first. In particular, the `0.3.0` script cannot replace itself and must be
replaced by hand as the `0.4.0` notes show.

**If you run `0.6.0-rc.2`.** `0.6.0` is built from the `0.6.0-rc.2` source
plus its release notes and version; no application code changes. The upgrade
from `0.6.0-rc.2` follows the same steps: the `0.6.0-rc.2` script also refuses
`0.6.0` as a newer release, so on Compose and Swarm run
`./setup.sh update-script`, back up, run `./setup.sh upgrade`, then on Compose
`./setup.sh start`. There is no migration and no chart change; only the images
change. On Kubernetes, run `helm upgrade` with `--version 0.6.0`.

Product version is `v0.6.0`, Git tag `hangar-v0.6.0`, Helm chart version
`0.6.0`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.6.0`.

## Known limitations and rollback

`0.6.0-rc.2` was the release candidate for this release and is superseded by
it; do not install it, and upgrade an installation on it to `0.6.0`.
`v0.6.0-rc.1` is a tag without a release: its container images are in GHCR,
but its `live` image does not start and its chart and GitHub Release were never
published, so do not deploy its images. The previous stable release, for
upgrades and rollback, is `0.5.0`. The release pipeline qualifies the Compose
upgrade from `0.5.0` before it publishes this release: `0.5.0` is installed
from its release assets, filled with data, backed up, upgraded with this
release's script, and the backup is restored into a fresh installation.

God Mode, the published boards and the whole web app now have the new design.
The editor's own toolbar, menus, code block and table colour picker keep their
Plane 1.4 components until the editor moves in a later release. The capacity
screens stay in English, as before. The web app's `custom` theme gets the
light treatment of the Hangar logo, which may not suit a dark custom palette.
The recorded upstream base stays Plane 1.4.0 with the 1.4.3 changes
backported.

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
- A page's PDF export prints a callout's emoji logo as its decimal code
  points, such as `128161`, instead of the emoji. The editor and the other
  exports show the emoji. This is unchanged from `0.5.0`.
- A page's PDF export can print a user mention as `@user_mention` instead of
  the user's name. The editor shows the name. This is unchanged from `0.5.0`.
- On Kubernetes this release is qualified for evaluation on AMD64 only: the
  production profile has still not completed qualification, so do not run the
  chart in production yet.

The all-in-one image does not send `Strict-Transport-Security` itself; put it
behind a proxy that adds it if you need it.

**Rolling back to `0.5.0`** needs no schema change and no change to the Helm
values: only the images change. An all-in-one installation that follows the
`stable` tag has to name `v0.5.0` to roll back, because `stable` now points to
`0.6.0`. Everything created on this release stays
readable there. Rolling back brings back the seed command that runs without an
opt-in, the callout logo that the editor's Markdown serializer writes
unchecked, the active cycles upsell page, the old callout logo picker, profile
activity rows that do not say what a worklog entry did, the sub-work items
filters without the work item type, and the Plane 1.4 components on the
screens that move here. The release check in this release's script never
refuses an older release, so it does not stand in the way of a rollback.
Rolling back to `0.6.0-rc.2` is not supported, because it is superseded, and
`v0.6.0-rc.1` is not a rollback target.
