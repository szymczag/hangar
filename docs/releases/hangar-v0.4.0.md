## Security and privacy

**The worker's log no longer shows password-reset tokens, sign-in codes or
invitation join tokens.** Up to and including `0.3.0`, and in upstream Plane,
the Celery worker logged every task it received, finished or failed at `INFO`,
with the task's arguments. Its JSON log format prints every field Celery hands
it, so the worker's log carried, in plain text:

- the password-reset link's user id and token (`forgot_password`);
- the sign-in code of a passwordless sign-in (`magic_link`);
- the confirmation code of an e-mail address change
  (`send_email_update_magic_code`);
- the join tokens of workspace and project invitations, with the invited
  address and the inviter (`workspace_invitation`, `project_invitation`).

Anyone who could read the worker's log, or a log store it is shipped to, could
reset that user's password, sign in as them or accept their invitation while
the token or code was still valid. The worker now writes `[redacted]` in place
of every task's arguments, positional and named. The task's name and id stay in
each line, so a line can still be traced to its task, and no line is dropped.
The worker's other log lines are unchanged.

> [!IMPORTANT]
> **Logs written before the upgrade are not rewritten.** Treat the worker
> logs of every earlier release, and every copy a log shipper or backup has
> taken of them, as sensitive: rotate or purge them, and restrict who can read
> what you keep. Consider any password-reset link or sign-in code issued while
> those logs were readable by someone other than its user as exposed. Links and
> codes expire on their own, and a user can ask for a new one at any time;
> an invitation that should not be accepted can be withdrawn. See
> [Upgrade](#migrations-and-compatibility) below for where each deployment
> keeps the worker's log.

**Published boards no longer reveal who is in the project.** Anyone with a
board's link can read its API (`/api/public/anchor/<anchor>/…`) without signing
in. Up to and including `0.3.0` that API named every project member, as
upstream Plane does by design: each work item carried `assignee_ids` and
`created_by`, `anchor/<anchor>/members/` listed every active member's display
name and avatar, voters and reactors came with their first and last names, and
comments, reactions and the board settings carried the users who created and
last changed them. The person filters also answered "is this user assigned to,
or mentioned in, anything here?" for any user id a visitor tried. The board now
names only the people who acted on it in public:

- Commenters, voters and reactors appear as a public actor with four fields:
  `id`, `display_name`, `avatar_url` and `is_bot`. The display name and avatar
  are what the board shows; the id lets a signed-in visitor's browser mark its
  own reactions, votes and comments. First and last names, the raw `avatar`
  field and every `created_by` and `updated_by` are gone, including the board
  settings, which named whoever published the board.
- Work items carry no `assignee_ids` and no `created_by`, and there is no member
  roster: `anchor/<anchor>/members/` now answers 404.
- Grouping or sub-grouping by `assignees__id` or `created_by` answers 400.
  Grouping by `created_by` used to fail with a server error.
- The `assignees`, `mentions`, `created_by`, `logged_by` and `subscriber`
  filters are ignored, and ordering by an assignee's name falls back to the
  default order. The `logged_by` filter used to fail with a server error.
- The intake that a signed-in visitor can read carries no assignees, and its
  person filters are ignored too.
- A mention in a description or comment renders as `@user`, or as the viewer's
  own name when it mentions the viewer. Spaces never loaded the member list it
  needed for names, so mentions used to read "@deactivated user".

Nothing visible is lost on the board: it never showed assignees. This is a
breaking change for other clients of the public API; see
[Breaking change for clients of the public board API](#migrations-and-compatibility)
below. [What a published board says about people](../authorization-model.md#what-a-published-board-says-about-people)
describes the rules in full.

**Workspace invitations are now an admin's act unless the instance hands them
to members.** The application's invitation endpoints
(`/api/workspaces/<slug>/invitations/`) let in members as well as admins,
although the permission they used is named for admins. Up to and including
`0.3.0`, and in upstream Plane, any workspace member could invite people at up
to their own role, change the role of any pending invitation and withdraw any
invitation, including one an admin had sent, and the pending-invitation list
showed every member every invitation's join link. From this release on:

- Workspace admins keep every right they had.
- Members get `403` on every invitation route, including the invitation policy,
  unless an operator turns on the new God Mode switch **Workspaces → Members can
  invite to workspaces** (`ALLOW_MEMBERS_TO_INVITE`). The switch is off after
  the upgrade; see the [upgrade note](#migrations-and-compatibility) below.
- With the switch on, a member can invite at up to their own role, as before,
  but lists, reads, re-roles and withdraws only the invitations they sent.
  Anyone else's invitation answers `404`, and the member's list carries only
  their own join links.
- Guests, deactivated members and outsiders are refused whatever the switch
  says. Only an exact `1` turns it on; a missing, empty or other value reads as
  off.
- The web app offers the invite button, the pending-invitation list, the role
  select and the copy-link and remove actions on an invitation, the sidebar's
  invite link and the home page's "Invite team" only where the server would
  accept them. It learns the switch from the signed-in instance configuration
  (`members_can_invite`), never from the anonymous one.

A member's own invitations are recognised by their recorded sender. Up to and
including `0.3.0`, and in upstream Plane, the task that sends the invitation
e-mail saved the invitation again in the worker, where there is no signed-in
user, and that save erased its sender. The task now writes only the e-mail's
text and keeps the sender. **Invitations sent before this release have no
recorded sender and stay admin-managed**: their sender cannot see or withdraw
them, and an admin can. A member who needs to manage one can ask an admin to
withdraw it and send it again.

The public API (`/api/v1/workspaces/<slug>/invitations/`) was already
admin-only and does not read the switch. The domain rules for invitations and
the cap at the inviter's own role still apply to every caller.
[Workspace invitations](../authorization-model.md#workspace-invitations)
describes the rules in full.

**An outdated setup.sh now refuses to install or upgrade to a newer
release.** `setup.sh` and `swarm.sh` never update themselves: `upgrade` fetches
the new release's deployment files but not the new script, so a fix that lives
in the script reaches an installation only when its operator downloads the new
one. In `0.3.0` that kept the `plane.env` permission fix away from every
installation upgraded with the `0.2.2` script. From this release on:

- Each published `setup.sh` and `swarm.sh` names the release it belongs to. The
  release workflow writes it into the script as `SCRIPT_RELEASE` before it
  computes and signs `SHA256SUMS`, so the checksums cover it.
- `install` and `upgrade` (Swarm: the first `deploy`, and `upgrade`) refuse to
  go to a newer release than the script's own. They stop before they ask,
  download, stop a service or change a file, print an `ERROR` that names both
  releases and the commands that download and verify the right script, and end
  with `Nothing has been changed`.
- `start`, `stop` and `restart` (Swarm: `deploy` with an existing
  configuration, `remove` and `redeploy`) only print a `WARNING` when the
  installed release is newer than the script, so a deployment can always be
  stopped or restarted.
- The same release, or an older one for a rollback, proceeds as before.
  `HANGAR_ALLOW_OLD_SCRIPT=1` or `--allow-old-script` installs or upgrades with
  an old script anyway, after one `WARNING`.
- A new action, `./setup.sh update-script`, downloads the script of the latest
  stable release, or of the one named in `HANGAR_RELEASE`, into a scratch
  folder beside the script. It verifies it as it verifies the deployment files
  (`SHA256SUMS`, and its Cosign signature when Cosign is installed), checks
  that it names that release, and renames it over the old script with mode
  `755` and the old owner. It never runs the new script, and a failed check
  leaves the old one as it was.
- An upgrade to the release named in `HANGAR_RELEASE` calls it the requested
  release (`Requested release: <release>`) and prints
  `INSTALLING RELEASE <release>`. On Compose the upgrade now ends with the
  command that starts the services.

> [!IMPORTANT]
> **The protection starts with this release's script, so replace the `0.3.0`
> script by hand once.** Scripts up to and including `0.3.0` do not know their
> own release and have no `update-script` action, so they cannot warn you. As
> `0.4.0` is a stable release, a `0.3.0` script's `./setup.sh upgrade` picks it
> on its own and goes ahead without any check of its own age, and the `0.3.0`
> script stays in place for the next upgrade. Download and verify this
> release's `setup.sh` (or `swarm.sh`) before you upgrade, as the
> [installation guide](../../deployments/cli/community/README.md#upgrading-hangar-version)
> describes and [Upgrade](#migrations-and-compatibility) below shows. After
> that, `./setup.sh update-script` replaces it for you and the script tells you
> when it is out of date.

**Setting a first password is now rate limited.** `POST /auth/set-password/`,
which sets the password of a signed-in account that has none yet, had no rate
limit at all: the default throttle skips a signed-in caller. It now has two, as
the e-mail change does: ten attempts an hour per account, and the per-address
`AUTHENTICATION_RATE_LIMIT` (default `10/minute`) that sign-in and the password
change already share. A refusal answers `429` with `RATE_LIMIT_EXCEEDED` and
leaves the account untouched. The federated refusal, the strength check and the
refusal of an account that already has a password are unchanged.

**The set-password page now shows the form that sets a password.**
`/accounts/set-password`, as in upstream Plane, rendered the reset form, which
needs the token from a reset e-mail and could only fail there. Nothing links to
the page any more; it is reachable only by its address. It now renders the form
for a signed-in account without a password, with the 15-character minimum, the
strength estimate and the CSRF token. A visitor without a session is sent to
sign in first. An account that already has a password is sent to **Profile →
Security**, and an account bound to an identity provider, or any account on an
instance with password sign-in switched off, sees a notice and no form. The
server's own checks decide in every case.

**A new API token's secret no longer stays in the page's token list.** After
creating a token, the web app (like upstream Plane) put the server's answer,
secret included, into the cached token list, where it outlived the dialog that
showed it. The cached row is now the answer without the secret. The secret is
shown once in the dialog, can be downloaded as before, and is dropped when the
dialog closes. The server never returned it from the list.

**The vote and reaction lists of a published board now return the board's own
data, and still name nobody.**
`GET /api/public/anchor/<anchor>/issues/<issue>/votes/` and `…/reactions/`
always answered an empty list: both looked the board up by a field their route
never supplies. They now find the board by its anchor, as adding a vote or
reaction already did, and list the votes and reactions of that one work item.
They answer only while the board is published and its votes or reactions are
enabled, and only for a work item the board itself shows: never for a draft,
archived or intake item, or one from another project. Both lists still need a
signed-in visitor, as before, and each row carries the four-field public actor
described above, never a name, email or `created_by`. They show nothing that
the work item's own `vote_items` and `reaction_items` do not already show.

**Spaces keeps its Content-Security-Policy on the new design and loads no
emoji data from a CDN.** Spaces, the server-rendered app that serves published
boards, keeps its per-request nonce policy. No hash, nonce source or exception
is added. The new components bring in Base UI; Spaces now hands it the
request's nonce, so the one script Base UI can write before the page hydrates
would carry it. No board page emits that script today. The emoji picker behind
the reaction button reads its data from this instance, under
`/spaces/emojibase/`, never from the public CDN that its library uses by
default and that the policy would refuse. A security test opens the picker on a
published board without an account and fails on any request that leaves the
instance's origin.

The web app's move to the new design, described below, adds no inline script
or style and no exception to its Content-Security-Policy, and its Trusted Types
policies are still installed before anything renders. Both of its emoji pickers
read their data from this instance, never from a CDN.

**The web app's move to the new design brings in none of upstream's external
services.** The screens that moved to Propel, described below, are upstream
Plane `1.5.0`'s, merged with Hangar's changes:

- The cover pickers (projects and the profile) offer the bundled images and an
  upload only. Upstream's `1.5.0` picker restores an Unsplash tab and search;
  Hangar's does not (S21), and the web app loads no image from another host.
- Upstream's help links, "Docs" buttons on the settings pages, "Learn more"
  links and star and issue links are not taken, or point at Hangar's own
  addresses. Every outbound link renders only where the instance allows
  external links. The command palette's documentation and bug-report commands
  now follow that switch too; up to `0.3.0` they showed regardless.
- Upstream's tracking attributes on the sign-in and project screens, its
  analytics, upgrade badges and plan comparisons are not taken.
- Every password screen keeps the 15-character minimum and the zxcvbn strength
  estimate, every form keeps its CSRF token and endpoint, and sign-in still
  follows `next_path` only to an address of this instance.
- The web app adds no inline script or style and no exception to its
  Content-Security-Policy. The one new script sink, Base UI's pre-hydration
  script, is an empty stub in the browser build and is recorded in the
  reviewed inventory.

## Migrations and compatibility

**Upgrade note: treat the worker logs written before this upgrade as
sensitive.** The upgrade does not rewrite or remove anything the worker logged
before it, and those lines hold password-reset tokens, sign-in and e-mail-change
codes and invitation join tokens, as the [security note](#security-and-privacy)
above describes. This affects every Hangar release up to and including `0.3.0`
and its `0.4.0` release candidates up to `0.4.0-rc.3`, and upstream Plane. The
worker's log is the output of each Celery worker: on Compose and Swarm the
container logs of the `worker`, `mail-worker` and `import-worker` services,
wherever your Docker log driver keeps or sends them; on Kubernetes the logs of
the chart's worker pods and your cluster's log collection; in the all-in-one
image `/app/logs/error/worker.err.log` and its rotated copies on the
`/app/logs` volume. After the upgrade, rotate or purge those logs and every
copy shipped or backed up from them, or restrict who can read what you must
keep. If anyone other than the user could read them, consider the
password-reset links and sign-in codes issued in that time exposed: they expire
on their own, and a user can request a new one; withdraw any pending invitation
that should not be accepted. No other step is needed.

**Upgrade note: workspace members can no longer invite people until an
operator turns the switch on.** After the upgrade from `0.3.0`, workspace
members can no longer invite people, change the role of a pending invitation or
withdraw one, and no longer see the pending-invitation list on the members
page. Their requests to the invitation endpoints answer `403`. This lasts until
an operator turns on **God Mode → Workspaces → Members can invite to
workspaces**. Even then, a member sees and manages only the invitations they
sent. Workspace admins are unaffected. **Invitations that are already pending
stay valid**: the people they were sent to can still accept them, and an admin
can still withdraw them. Turning the switch off later takes the right back from
members at once, including over invitations they sent while it was on. If
members of your workspaces invite people, decide before the upgrade whether to
turn the switch on straight after it. Invitations sent before this release have
no recorded sender, as described [above](#security-and-privacy), so with the
switch on a member manages only the invitations they send from this release on.

**The web app moves to the new upstream 1.5.0 design: its design tokens
everywhere, and the shell, sign-in and onboarding, projects and settings on the
new components.** The web app's stylesheet now carries Propel's colour,
typography and spacing tokens, and every screen renders on them. These screens
also move onto the Propel and `@plane/blocks` components from upstream Plane
`v1.5.0`, merged with Hangar's changes, as God Mode already is and the
published boards now are:

- The shell: the sidebar, the workspace switcher, the top navigation, the app
  rail and the page header, which is 4 pixels taller. "Workspace" in the
  sidebar becomes a collapsible group, and the workspace switcher shows the
  workspace's initials. Hangar's help menu, capacity entries and "Duplicate
  project" stay.
- The command palette, its shortcut sheet and the shared dialogs, such as bulk
  delete and adding existing work items.
- The property pickers (state, priority, assignees, estimate, cycle, module,
  project and dates), everywhere they appear, including the work item lists.
  A date range is set once both days are picked rather than on the first click,
  and a date is cleared with the calendar's "Clear" action instead of the ×
  on its button.
- Sign-in, sign-up, the unique code, forgot, reset and set password, the
  provider buttons, the invitation pages and onboarding. Onboarding now stays
  on the workspace step when it is reloaded after the profile step; it used to
  go back to the profile step.
- The projects list and its cards, project creation, including starting from
  an existing project, and the project settings: general, members, features,
  states, labels, estimates and automations. **Deleting or leaving a project
  now asks for the project's name only**, as upstream does; `0.3.0` also asked
  for a fixed phrase, "delete my project" or "Leave Project". Deleting a
  workspace still asks for both its name and "delete my workspace".
- The workspace settings (general, members and invitations, exports, webhooks,
  integrations) and the account settings (general, preferences, notifications,
  security and API tokens). Exports now start from an "Export" button that
  opens a dialog.

Colours, sizes and spacing on these screens follow upstream's new design. On
the screens that keep their Plane 1.4 components, the tokens shift colours,
font weights, line heights and letter-spacing slightly compared with `0.3.0`:
some light-mode greys are a little darker, accent, danger and warning tints
move by a step, regular text is slightly heavier, body lines are a little
taller and text a little wider, so lists and cards grow by a few pixels. Menus
still open above dialogs. The web app also waits for its translations to load
before it hydrates; a failed translation load does not stop the app from
starting. Permissions, endpoints and what each screen can do are unchanged,
apart from the invitation rules above. Reload open web app tabs after the
upgrade. What still keeps the Plane 1.4 components is listed under
[Known limitations](#known-limitations-and-rollback).

**The published boards move to the new upstream 1.5.0 design.** Spaces now
uses the Propel component library and the `@plane/blocks` components from
upstream Plane `v1.5.0`, as God Mode has since `0.3.0`: the sign-in forms,
filters, list and board layouts, property chips, the side panel with its
activity and comments, reactions and votes, the navigation bar and toasts. The
Hangar name and mark, the error page and the terms links stay Hangar's. The
sign-up form keeps Hangar's password rules: at least 15 characters and a strong
enough strength estimate. Upstream's new boards show every work-item property,
assignees included; **Hangar's boards still show only the key, state, priority,
labels and due date.** The side panel gains a labels row, and labels were
already on the cards.

**The first reaction on a published work item now saves.** On a work item
nobody had reacted to, Spaces dropped the reaction before it sent it: the board
API answered `null` instead of an empty list for `reaction_items` and
`vote_items`, and Spaces failed on it. The API now answers an empty list on the
work item and on the board's lists, grouped or not, and Spaces tolerates `null`
from an older server. A failed vote or reaction no longer leaves the work item
showing rows it cannot read.

**Page version history is now recorded.** No earlier Hangar release recorded
it. Every page save started a background task that failed on a field upstream
Plane had renamed (`AttributeError: 'Page' object has no attribute
'description'`), and the task only logged the error, so the save itself
succeeded and the page's version history stayed empty. Upstream Plane `v1.5.0`
has the same bug. Saving a page now records a version: a user's saves within
ten minutes update that user's latest version, and a page keeps at most its 20
most recent versions. **Versions are recorded from the upgrade on, not for
earlier edits**: history before it cannot be recovered. The fix needs no
migration. The version history panel and its endpoints are unchanged. Anyone
who can open a page can open its history, under the same project and guest
rules as the page itself, so text removed from a page stays readable in its
earlier versions until they age out.

**Breaking change for clients of the public board API.** A script,
integration or embedded board that reads `/api/public/` must change if it uses
any of:

- `assignee_ids` or `created_by` on a work item (list, grouped list and
  detail): no longer returned;
- `anchor/<anchor>/members/`: removed, now 404;
- `actor_details` or `actor_detail` on votes, reactions and comments: reduced to
  `id`, `display_name`, `avatar_url` and `is_bot`;
- `created_by` or `updated_by` on comments, reactions or the board settings: no
  longer returned;
- `assignees` or `assignee_details` on the intake: no longer returned;
- `group_by` or `sub_group_by` set to `assignees__id` or `created_by`: refused
  with 400;
- the `assignees`, `mentions`, `created_by`, `logged_by` and `subscriber`
  filters, and `order_by=assignees__first_name`: ignored.

`vote_items` and `reaction_items` are an empty list rather than `null` on a
work item without votes or reactions, and the votes and reactions lists return
data, as described above. The API-token API (`/api/v1/`) is unchanged, and so
are the board's metadata, states, labels, cycles and modules. Of the signed-in
application's endpoints, only the workspace invitation endpoints change, as
described above.

**One license migration and no chart change.** Compared with `0.3.0`, this
release adds one license migration, `0025`, and no database migration. It
changes no table: it only adds the `ALLOW_MEMBERS_TO_INVITE` row to the
instance configuration, with the value `0`, and never overwrites a row that is
already there. The value can also come from an `ALLOW_MEMBERS_TO_INVITE`
environment variable in the migration's container, which neither the Compose
files nor the chart set. The migrations lockfile names
`license: 0025_allow_members_to_invite`. The migration runs with the others on
upgrade (on Compose, in the `migrator` service) and needs no step of its own.
The Helm chart's templates, values and Secrets do not change. The Compose and
Swarm deployment contract does not change either: `variables.env` is the same,
and the published `docker-compose.yml` keeps its services, settings and
variables. The file itself does change, as it does in every release: its header
names `v0.4.0`, and it pins the Hangar images to this release's digests. Each
release builds all seven Hangar images (`web`, `admin`, `space`, `live`, `api`,
`proxy` and the all-in-one `aio`) afresh, with the release's version and
refreshed Alpine packages, so every image digest changes. Compared with
`0.3.0`, the `api`, `web`, `space` and `admin` images carry the changes
described here; the Celery workers, the scheduler and the migrator run the
`api` image, and the all-in-one image bundles them all. `setup.sh` and
`swarm.sh` change as described above. The in-app release notes in the web app
name this release.

Upgrade from `0.3.0`. The installers pick `0.4.0` on their own, but only this
release's script checks its own age, so on Compose and Swarm:

1. Replace the script with this release's, by hand, because the `0.3.0` script
   cannot replace itself. Do not download the new script straight over the old
   one: fetch it with the release's `SHA256SUMS` and
   `SHA256SUMS.sigstore.json` into a folder of its own next to `plane-app/`,
   check it, and only then copy it into place:

   ```sh
   mkdir -p hangar-v0.4.0 && cd hangar-v0.4.0
   curl -fsSL -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0/setup.sh \
     -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0/SHA256SUMS \
     -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0/SHA256SUMS.sigstore.json
   cosign verify-blob --bundle SHA256SUMS.sigstore.json \
     --certificate-identity https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/hangar-v0.4.0 \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS
   sha256sum --check --ignore-missing SHA256SUMS
   cd .. && cp hangar-v0.4.0/setup.sh ./setup.sh && chmod 755 ./setup.sh
   ```

   On macOS use `shasum -a 256 --check --ignore-missing SHA256SUMS`. If either
   check fails, stop: your old script is untouched. On Swarm, download
   `swarm.sh` instead and copy `hangar-v0.4.0/swarm.sh` over your `setup.sh`.
   [Upgrading Hangar Version](../../deployments/cli/community/README.md#upgrading-hangar-version)
   explains each command.

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
   `0.4.0`, the latest stable release.
4. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES` and the command that starts them:
   check `plane-app/plane.env`, then run `./setup.sh start`. Hangar stays down
   until you do. On Swarm, the upgrade redeploys the stack itself.
5. If workspace members should keep inviting people, turn on **God Mode →
   Workspaces → Members can invite to workspaces**, as the upgrade note above
   describes.
6. Rotate or purge the worker logs written before the upgrade, as the upgrade
   note above describes.
7. For later releases, run `./setup.sh update-script` (or
   `HANGAR_RELEASE=<release> ./setup.sh update-script` for a named release)
   before `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells
   you what to run. `update-script` checks the Cosign signature of
   `SHA256SUMS` only when `cosign` is installed; without it, it prints a
   `WARNING` and compares the script only with the `SHA256SUMS` downloaded
   beside it. Add `HANGAR_REQUIRE_SIGNATURE=1` to make the signature check
   mandatory: without Cosign the command then refuses and leaves the old script
   in place.

Use the `v0.4.0` all-in-one image, which the `stable` tag now also points to,
or run `helm upgrade` with `--version 0.4.0` on Kubernetes. Neither needs a
further step for the migration; decide about the invitation switch as in step
5, and deal with the worker logs as in step 6. Reload open web app tabs and
published boards after the upgrade. Upgrading from a release older than
`0.3.0` also brings what the [`0.3.0` notes](hangar-v0.3.0.md) and the
releases before it describe; read them first. In particular, an upgrade from
`0.2.2` or older needs this release's script for the `plane.env` permission fix
as well.

**If you run a `0.4.0` release candidate.** `0.4.0` is built from the
`0.4.0-rc.4` source plus its release notes and version. From `0.4.0-rc.4` the
upgrade changes only the images: there is no migration and no chart change,
the application code is the same apart from the in-app release notes, and the
invitation switch keeps its value. The `0.4.0-rc.4`
script still refuses `0.4.0` as a newer release, so on Compose and Swarm run
`./setup.sh update-script`, then `./setup.sh upgrade`, then on Compose
`./setup.sh start`. From `0.4.0-rc.1`, `0.4.0-rc.2` or `0.4.0-rc.3` the steps
are the same, with these additions. From `0.4.0-rc.1` or `0.4.0-rc.2`, the
upgrade runs migration `0025` and turns the invitation switch off (step 5
applies). From any candidate up to `0.4.0-rc.3`, the worker logs need rotating
(step 6). Page versions are recorded from `0.4.0-rc.2` on. On Kubernetes, run
`helm upgrade` with `--version 0.4.0`.

Product version is `v0.4.0`, Git tag `hangar-v0.4.0`, Helm chart version
`0.4.0`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.4.0`.

## Known limitations and rollback

`0.4.0-rc.1`, `0.4.0-rc.2`, `0.4.0-rc.3` and `0.4.0-rc.4` were release
candidates for this release and are superseded by it; do not install them, and
upgrade an installation on any of them to `0.4.0`. The previous stable release,
for upgrades and rollback, is `0.3.0`. The release pipeline qualifies the
Compose upgrade from `0.3.0` before it publishes this release: `0.3.0` is
installed from its release assets, filled with data, backed up, upgraded with
this release's script, and the backup is restored into a fresh installation.

God Mode and the published boards have the new design, and so do the web app's
shell, sign-in and onboarding, projects and settings. The rest of the web app,
including the work items and their lists, cycles, modules, views, pages,
intake, notifications and the profile pages, keeps its Plane 1.4 components
until they move in later releases; its property pickers already render the new
ones. Hangar's own settings pages (home defaults, imports, workshop templates,
and the e-mail security and receipts sections) also keep their 1.4 controls
inside the new settings pages.

- Choosing "No estimate" on a work item still does not clear an estimate that
  is already set, as in `0.3.0`; this is fixed when the work item screens move.
- In light mode, the General page of a project's settings shows the name of a
  project without a cover image in white on a white background.
- In light mode, the Hangar logo on the sign-in and sign-up pages has little
  contrast against the page.
- Invitations sent before this release have no recorded sender and stay with
  admins, as described above.
- Page history starts with the upgrade (from `0.4.0-rc.2` for an installation
  that ran a candidate); edits made before that have no versions.
- A mention keeps the mentioned user's id in the stored text of a description
  or comment, so a visitor of a published board can tell that some account was
  mentioned, but nothing on the board turns the id into a name.
- Scripts up to `0.3.0` cannot detect that they are out of date, as described
  above; replace yours by hand once.
- On Kubernetes this release is qualified for evaluation on AMD64 only: the
  production profile has still not completed qualification, so do not run the
  chart in production yet.

The recorded upstream base stays Plane 1.4.0 with the 1.4.3 changes
backported. The all-in-one image does not send `Strict-Transport-Security`
itself; put it behind a proxy that adds it if you need it.

**Rolling back to `0.3.0`** needs no schema change and no change to the Helm
values: only the images change. An all-in-one installation that follows the
`stable` tag has to name `v0.3.0` to roll back, because `stable` now points to
`0.4.0`. Migration `0025` only added a configuration row, which `0.3.0` does
not read; leave it in place. `0.3.0` does not know the migration and starts
normally with it recorded, and an upgrade again later keeps the value the row
holds. Rolling back brings back:

- the worker's log of task arguments, with the reset tokens, sign-in and
  e-mail-change codes and join tokens in it, and the invitation e-mail task
  that erases an invitation's sender;
- a public board API that names every project member and assignee, the empty
  vote and reaction lists and the lost first reaction;
- workspace members who can invite people and change or withdraw any pending
  invitation, whatever the switch says;
- the first-password endpoint without a rate limit, the set-password page that
  shows the reset form, and a new API token's secret kept in the cached token
  list;
- the previous look of the published boards, and the whole web app on its
  previous design tokens and components.

`0.3.0` records no page versions; those recorded since the upgrade stay in the
database and stay readable in the history panel, but no new ones are added. The
release check in this release's script never refuses an older release, so it
does not stand in the way of a rollback. Rolling back to a `0.4.0` release candidate is not supported,
because they are superseded.
