## Security and privacy

**The worker's log no longer shows password-reset tokens, sign-in codes or
invitation join tokens.** New in this candidate. Up to and including
`0.4.0-rc.3`, and in upstream Plane, the Celery worker logged every task it
received, finished or failed at `INFO`, with the task's arguments. Its JSON log
format prints every field Celery hands it, so the worker's log carried, in
plain text:

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

**A member who sends an invitation can now see and manage it.** New in this
candidate. With **Members can invite to workspaces** on, `0.4.0-rc.3` let a
member see, re-role and withdraw only the invitations they sent. But the task
that sends the invitation e-mail saved the invitation again in the worker,
where there is no signed-in user, and that save erased its sender. Every
invitation therefore ended up with no recorded sender, and the member who sent
it got an empty list and `404` on it. The check failed closed: admins were
unaffected, and no member saw or changed anyone else's invitation. The task now
writes only the e-mail's text and keeps the sender. **Invitations sent before
this release have no recorded sender and stay admin-managed**: their sender
cannot see or withdraw them, and an admin can. A member who needs to manage one
can ask an admin to withdraw it and send it again.

**Workspace invitations are now an admin's act unless the instance hands them
to members.** This carries over from `0.4.0-rc.3`. The application's invitation endpoints
(`/api/workspaces/<slug>/invitations/`) let in members as well as admins,
although the permission they used is named for admins. Up to and including
`0.4.0-rc.2`, and in upstream Plane, any workspace member could invite people
at up to their own role, change the role of any pending invitation and withdraw
any invitation, including one an admin had sent, and the pending-invitation
list showed every member every invitation's join link. From `0.4.0-rc.3` on:

- Workspace admins keep every right they had.
- Members get `403` on every invitation route, including the invitation policy,
  unless an operator turns on the new God Mode switch **Workspaces → Members can
  invite to workspaces** (`ALLOW_MEMBERS_TO_INVITE`). The switch is off after
  the upgrade; see the [upgrade note](#migrations-and-compatibility) below.
- With the switch on, a member can invite at up to their own role, as before,
  but lists, reads, re-roles and withdraws only the invitations they sent.
  Anyone else's invitation answers `404`, and the member's list carries only
  their own join links. An invitation with no recorded sender is left to admins.
- Guests, deactivated members and outsiders are refused whatever the switch
  says. Only an exact `1` turns it on; a missing, empty or other value reads as
  off.
- The web app offers the invite button, the pending-invitation list, the role
  select and the copy-link and remove actions on an invitation, the sidebar's
  invite link and the home page's "Invite team" only where the server would
  accept them. It learns the switch from the signed-in instance configuration
  (`members_can_invite`), never from the anonymous one.

The public API (`/api/v1/workspaces/<slug>/invitations/`) was already
admin-only and does not read the switch. The domain rules for invitations and
the cap at the inviter's own role still apply to every caller.
[Workspace invitations](../authorization-model.md#workspace-invitations)
describes the rules in full.

**Setting a first password is now rate limited.** This carries over from
`0.4.0-rc.3`.
`POST /auth/set-password/`, which sets the password of a signed-in account that
has none yet, had no rate limit at all: the default throttle skips a signed-in
caller. It now has two, as the e-mail change does: ten attempts an hour per
account, and the per-address `AUTHENTICATION_RATE_LIMIT` (default `10/minute`)
that sign-in and the password change already share. A refusal answers `429`
with `RATE_LIMIT_EXCEEDED` and leaves the account untouched. The federated
refusal, the strength check and the refusal of an account that already has a
password are unchanged.

**The set-password page now shows the form that sets a password.** This
carries over from `0.4.0-rc.3`. `/accounts/set-password`, as in upstream Plane, rendered the reset
form, which needs the token from a reset e-mail and could only fail there.
Nothing links to the page any more; it is reachable only by its address. It now
renders the form for a signed-in account without a password, with the
15-character minimum, the strength estimate and the CSRF token. A visitor
without a session is sent to sign in first. An account that already has a
password is sent to **Profile → Security**, and an account bound to an identity
provider, or any account on an instance with password sign-in switched off, sees
a notice and no form. The server's own checks decide in every case.

**A new API token's secret no longer stays in the page's token list.** This
carries over from `0.4.0-rc.3`. After creating a token, the web app (like upstream Plane) put
the server's answer, secret included, into the cached token list, where it
outlived the dialog that showed it. The cached row is now the answer without
the secret. The secret is shown once in the dialog, can be downloaded as
before, and is dropped when the dialog closes. The server never returned it
from the list.

**The web app's move to the new design brings in none of upstream's external
services.** This carries over from `0.4.0-rc.3`. The screens that moved to
Propel there, described
below, are upstream Plane `1.5.0`'s, merged with Hangar's changes:

- The cover pickers (projects and the profile) offer the bundled images and an
  upload only. Upstream's `1.5.0` picker restores an Unsplash tab and search;
  Hangar's does not (S21), and the web app loads no image from another host.
- Upstream's help links, "Docs" buttons on the settings pages, "Learn more"
  links and star and issue links are not taken, or point at Hangar's own
  addresses. Every outbound link renders only where the instance allows
  external links. The command palette's documentation and bug-report commands
  now follow that switch too; up to `0.4.0-rc.2` they showed regardless.
- Upstream's tracking attributes on the sign-in and project screens, its
  analytics, upgrade badges and plan comparisons are not taken.
- Every password screen keeps the 15-character minimum and the zxcvbn strength
  estimate, every form keeps its CSRF token and endpoint, and sign-in still
  follows `next_path` only to an address of this instance.
- The web app adds no inline script or style and no exception to its
  Content-Security-Policy. The one new script sink, Base UI's pre-hydration
  script, is an empty stub in the browser build and is recorded in the
  reviewed inventory.

**Published boards no longer reveal who is in the project.** This carries over
from `0.4.0-rc.1`. Anyone with a board's link can read its API
(`/api/public/anchor/<anchor>/…`) without signing in. Up to and including
`0.3.0` that API named every project member, as upstream Plane does by design:
each work item carried `assignee_ids` and `created_by`,
`anchor/<anchor>/members/` listed every active member's display name and
avatar, voters and reactors came with their first and last names, and
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

**An outdated setup.sh now refuses to install or upgrade to a newer
release.** This carries over from `0.4.0-rc.1`. `setup.sh` and `swarm.sh`
never update themselves: `upgrade` fetches the new release's deployment files
but not the new script, so a fix that lives in the script reaches an
installation only when its operator downloads the new one. In `0.3.0` that
kept the `plane.env` permission fix away from every installation upgraded with
the `0.2.2` script. From `0.4.0-rc.1` on:

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
  release, or of the one named in `HANGAR_RELEASE`, into a scratch folder beside
  the script. It verifies it as it verifies the deployment files (`SHA256SUMS`,
  and its Cosign signature when Cosign is installed), checks that it names that
  release, and renames it over the old script with mode `755` and the old
  owner. It never runs the new script, and a failed check leaves the old one as
  it was.

> [!IMPORTANT]
> **The protection starts with the `0.4.0-rc.1` script.** Scripts up to and
> including `0.3.0` do not know their own release and have no `update-script`
> action, so they cannot warn you. Replace your `setup.sh` (or `swarm.sh`) by
> hand once, as the
> [installation guide](../../deployments/cli/community/README.md#upgrading-hangar-version)
> describes and [Upgrade](#migrations-and-compatibility) below shows. After
> that, `./setup.sh update-script` replaces it for you and the script tells you
> when it is out of date.

**The vote and reaction lists of a published board now return the board's own
data, and still name nobody.** This carries over from `0.4.0-rc.2`.
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
emoji data from a CDN.** This carries over from `0.4.0-rc.1`. Spaces, the
server-rendered app that serves published boards, keeps its per-request nonce
policy. No hash, nonce source or exception is added. The new components bring
in Base UI; Spaces now hands it the request's nonce, so the one script Base UI
can write before the page hydrates would carry it. No board page emits that
script today. The emoji picker behind the reaction button reads its data from
this instance, under `/spaces/emojibase/`, never from the public CDN that its
library uses by default and that the policy would refuse. A new security test
opens the picker on a published board without an account and fails on any
request that leaves the instance's origin.

The web app's move to the new design tokens in `0.4.0-rc.2` added no inline
script or style and no exception to its Content-Security-Policy, and its
Trusted Types policies are still installed before anything renders. Both of
its emoji pickers read their data from this instance, never from a CDN.

## Migrations and compatibility

**Upgrade note: treat the worker logs written before this upgrade as
sensitive.** New in this candidate. The upgrade does not rewrite or remove
anything the worker logged before it, and those lines hold password-reset
tokens, sign-in and e-mail-change codes and invitation join tokens, as the
[security note](#security-and-privacy) above describes. This affects every
Hangar release up to and including `0.4.0-rc.3`, and upstream Plane. The
worker's log is the output of each Celery worker: on Compose and Swarm the
container logs of the `worker`, `mail-worker` and `import-worker` services,
wherever your Docker log driver keeps or sends them; on Kubernetes the logs of
the chart's worker pods and your cluster's log collection; in the all-in-one
image `/app/logs/error/worker.err.log` and its rotated copies on the
`/app/logs` volume. After the upgrade, rotate or purge those logs and every copy shipped
or backed up from them, or restrict who can read what you must keep. If anyone
other than the user could read them, consider the password-reset links and
sign-in codes issued in that time exposed: they expire on their own, and a user
can request a new one; withdraw any pending invitation that should not be
accepted. No other step is needed.

**Upgrade note: workspace members can no longer invite people until an
operator turns the switch on.** This carries over from `0.4.0-rc.3` and
applies when you upgrade from `0.3.0`, `0.4.0-rc.2` or `0.4.0-rc.1`; from
`0.4.0-rc.3` the switch keeps the value you gave it. After the upgrade,
workspace members can no longer invite people, change the role of a pending
invitation or withdraw one, and no longer see the pending-invitation list on
the members page. Their requests to the invitation endpoints answer `403`.
This lasts until an operator turns on **God Mode → Workspaces → Members can
invite to workspaces**. Even then, a member sees and manages only the
invitations they sent. Workspace admins are unaffected. **Invitations that are
already pending stay valid**: the people they were sent to can still accept
them, and an admin can still withdraw them. Turning the switch off later takes
the right back from members at once, including over invitations they sent
while it was on. If members of your workspaces invite people, decide before
the upgrade whether to turn the switch on straight after it. Invitations sent
before this release have no recorded sender, as described
[above](#security-and-privacy), so with the switch on a member manages only
the invitations they send from this release on.

**The web app's shell, sign-in and onboarding, projects and settings move to
the new upstream 1.5.0 design.** This carries over from `0.4.0-rc.3`.
`0.4.0-rc.2` gave the web app the Propel design tokens; `0.4.0-rc.3` moved
these screens onto the
Propel and `@plane/blocks` components from upstream Plane `v1.5.0`, merged
with Hangar's changes, as God Mode and the published boards already are:

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
  now asks for the project's name only**, as upstream does; `0.4.0-rc.2` also
  asked for a fixed phrase, "delete my project" or "Leave Project". Deleting a
  workspace still asks for both its name and "delete my workspace".
- The workspace settings (general, members and invitations, exports, webhooks,
  integrations) and the account settings (general, preferences, notifications,
  security and API tokens). Exports now start from an "Export" button that
  opens a dialog.

Colours, sizes and spacing on these screens follow upstream's new design.
Permissions, endpoints and what each screen can do are unchanged, apart from
the invitation rules above. Reload open web app tabs after the upgrade.

**The web app loads the new upstream 1.5.0 design tokens.** This carries over
from `0.4.0-rc.2`. The web app's stylesheet carries Propel's colour, typography
and spacing tokens, and every screen renders on them, including those that
keep their Plane 1.4 components. Colours, font weights, line heights and
letter-spacing shift slightly compared with `0.3.0`: some light-mode greys are
a little darker, accent, danger and warning tints move by a step, regular text
is slightly heavier, body lines are a little taller and text a little wider, so
lists and cards grow by a few pixels. Menus still open above dialogs. The web
app also waits for its translations to load before it hydrates; a failed
translation load does not stop the app from starting.

**Page version history is now recorded.** This carries over from
`0.4.0-rc.2`. No Hangar release before it recorded it. Every page save started
a background task that failed on a field upstream Plane had renamed
(`AttributeError: 'Page' object has no attribute 'description'`), and the task
only logged the error, so the save itself succeeded and the page's version
history stayed empty. Upstream Plane `v1.5.0` has the same bug. Saving a page
now records a version: a user's saves within ten minutes update that user's
latest version, and a page keeps at most its 20 most recent versions.
**Versions are recorded from `0.4.0-rc.2` on, not for earlier edits**: history
before that upgrade cannot be recovered. The version history panel and its
endpoints are unchanged. Anyone who can open a page can open its history,
under the same project and guest rules as the page itself, so text removed from
a page stays readable in its earlier versions until they age out.

**The first reaction on a published work item now saves.** This carries over
from `0.4.0-rc.2`. On a work item nobody had reacted to, Spaces dropped the
reaction before it sent it: the board API answered `null` instead of an empty
list for `reaction_items` and `vote_items`, and Spaces failed on it. The API
now answers an empty list on the work item and on the board's lists, grouped
or not, and Spaces tolerates `null` from an older server. A failed vote or
reaction no longer leaves the work item showing rows it cannot read.

**The published boards move to the new upstream 1.5.0 design.** This carries
over from `0.4.0-rc.1`. Spaces now uses the Propel component library and the
`@plane/blocks` components from upstream Plane `v1.5.0`, as God Mode has since
`0.3.0`: the sign-in forms, filters, list and board layouts, property chips,
the side panel with its activity and comments, reactions and votes, the
navigation bar and toasts. The Hangar name and mark, the error page and the
terms links stay Hangar's. The sign-up form keeps Hangar's password rules: at
least 15 characters and a strong enough strength estimate. Upstream's new
boards show every work-item property, assignees included; **Hangar's boards
still show only the key, state, priority, labels and due date.** The side panel
gains a labels row, and labels were already on the cards.

**Breaking change for clients of the public board API.** This carries over
from `0.4.0-rc.1`. A script, integration or embedded board that reads
`/api/public/` must change if it uses any of:

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

Since `0.4.0-rc.2`, `vote_items` and `reaction_items` are an empty list rather
than `null` on a work item without votes or reactions, and the votes and
reactions lists return data, as described above. The API-token API
(`/api/v1/`) is unchanged, and so are the board's metadata, states, labels,
cycles and modules. Of the signed-in application's endpoints, only the
workspace invitation endpoints change, as described above.

**No migration since `0.4.0-rc.3`, and no chart change.** This release adds
no database or license migration compared with `0.4.0-rc.3`. Compared with
`0.3.0`, `0.4.0-rc.2` and `0.4.0-rc.1`, it adds the one license migration that
`0.4.0-rc.3` introduced, `0025`. It changes no table: it only adds the
`ALLOW_MEMBERS_TO_INVITE` row to the instance configuration, with the value
`0`, and never overwrites a row that is already there, so an installation on
`0.4.0-rc.3` keeps the value its operator set. The value can also come from an
`ALLOW_MEMBERS_TO_INVITE` environment variable in the migration's container,
which neither the Compose files nor the chart set. The migrations lockfile
names `license: 0025_allow_members_to_invite`. The migration runs with the
others on upgrade (on Compose, in the `migrator` service) and needs no step of
its own. The Helm chart's templates, values and Secrets do not change. The
Compose and Swarm deployment contract does not change either: `variables.env`
is the same, and the published `docker-compose.yml` keeps its services,
settings and variables. The file itself does change, as it does in every
release: its header names `v0.4.0-rc.4`, and it pins the Hangar images to this
release's digests.

**Every image is rebuilt; only `api` carries a code change since
`0.4.0-rc.3`.** New in this candidate. Each release builds all seven Hangar
images (`web`, `admin`, `space`, `live`, `api`, `proxy` and the all-in-one
`aio`) afresh, with the release's version and refreshed Alpine packages, so
every image digest changes from one release to the next. Of the application
code, only `api` changes since `0.4.0-rc.3`: the worker's log redaction and the
invitation sender fix described above. The Celery workers, the scheduler and
the migrator run the `api` image, and the all-in-one image bundles it. The
`web` image changes only in its in-app release notes, which name this release.
The `admin`, `space`, `live` and `proxy` code is unchanged. **The
`0.4.0-rc.3` notes were inaccurate here**: they said three images changed
compared with `0.4.0-rc.2`. Every image digest changed in that release too;
three images, `api`, `web` and `admin`, carried code changes. `setup.sh` and
`swarm.sh` are unchanged since `0.4.0-rc.3`, apart from the release each names
(`SCRIPT_RELEASE`), which the release workflow writes into them.

Upgrade from `0.3.0` or `0.4.0-rc.3`. This is a release candidate, so the
installers do not pick it on their own. On Compose and Swarm:

1. Replace the script with this release's.
   - **From `0.4.0-rc.3`** (or `0.4.0-rc.2` or `0.4.0-rc.1`), let the script
     replace itself:
     `HANGAR_RELEASE=v0.4.0-rc.4 ./setup.sh update-script`. It downloads and
     verifies the new script and changes nothing if a check fails. It checks
     the Cosign signature of `SHA256SUMS` only when `cosign` is installed;
     without it, it prints a `WARNING` and compares the script only with the
     `SHA256SUMS` downloaded beside it. Add `HANGAR_REQUIRE_SIGNATURE=1` to make
     the signature check mandatory: without Cosign the command then refuses and
     leaves the old script in place.
   - **From `0.3.0`**, replace it by hand, because the `0.3.0` script cannot
     replace itself. Do not download the new script straight over the old one:
     fetch it with the release's `SHA256SUMS` and `SHA256SUMS.sigstore.json`
     into a folder of its own next to `plane-app/`, check it, and only then
     copy it into place:

     ```sh
     mkdir -p hangar-v0.4.0-rc.4 && cd hangar-v0.4.0-rc.4
     curl -fsSL -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.4/setup.sh \
       -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.4/SHA256SUMS \
       -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.4/SHA256SUMS.sigstore.json
     cosign verify-blob --bundle SHA256SUMS.sigstore.json \
       --certificate-identity https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/hangar-v0.4.0-rc.4 \
       --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS
     sha256sum --check --ignore-missing SHA256SUMS
     cd .. && cp hangar-v0.4.0-rc.4/setup.sh ./setup.sh && chmod 755 ./setup.sh
     ```

     On macOS use `shasum -a 256 --check --ignore-missing SHA256SUMS`. If
     either check fails, stop: your old script is untouched. On Swarm,
     download `swarm.sh` instead and copy `hangar-v0.4.0-rc.4/swarm.sh` over
     your `setup.sh`.
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
3. Run `HANGAR_RELEASE=v0.4.0-rc.4 ./setup.sh upgrade`, as the owner of
   `plane-app/` or as root. This release's script names the candidate as the
   requested release (`Requested release: v0.4.0-rc.4`) and prints
   `INSTALLING RELEASE v0.4.0-rc.4`.
4. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES` and the command that starts them:
   check `plane-app/plane.env`, then run `./setup.sh start`. Hangar stays down
   until you do. On Swarm, the upgrade redeploys the stack itself.
5. From `0.3.0`, `0.4.0-rc.2` or `0.4.0-rc.1`: if workspace members should
   keep inviting people, turn on **God Mode → Workspaces → Members can invite
   to workspaces**, as the upgrade note above describes. From `0.4.0-rc.3` the
   switch keeps its value.
6. Rotate or purge the worker logs written before the upgrade, as the upgrade
   note above describes.
7. For later releases, run `HANGAR_RELEASE=<release> ./setup.sh update-script`
   (or plain `./setup.sh update-script` for the latest stable release) before
   `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells you what
   to run.

Use the `v0.4.0-rc.4` all-in-one image, or run `helm upgrade` with
`--version 0.4.0-rc.4` on Kubernetes. Neither needs a further step for the
migration; decide about the invitation switch as in step 5, and deal with the
worker logs as in step 6. Reload open web
app tabs and published boards after the upgrade. Upgrading from a release
older than `0.3.0` also brings what the [`0.3.0` notes](hangar-v0.3.0.md) and
the releases before it describe; read them first. In particular, an upgrade
from `0.2.2` or older needs this release's script for the `plane.env`
permission fix as well.

Product version is `v0.4.0-rc.4`, Git tag `hangar-v0.4.0-rc.4`, Helm chart
version `0.4.0-rc.4`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.4.0-rc.4`.

## Known limitations and rollback

This is a release candidate for `0.4.0`. `0.3.0` stays the current stable
release, and the installers keep choosing it unless you name this release.
`0.4.0-rc.3`, `0.4.0-rc.2` and `0.4.0-rc.1` are superseded by this candidate:
do not install them, and upgrade an installation on any of them to
`0.4.0-rc.4`.

God Mode and the published boards have the new design, and so do the web
app's shell, sign-in and onboarding, projects and settings. The rest of the web
app, including the work items and their lists, cycles, modules, views, pages,
intake, notifications and the profile pages, keeps its Plane 1.4 components
until they move in later releases; its property pickers already render the new
ones. Hangar's own settings pages (home defaults, imports, workshop templates,
and the e-mail security and receipts sections) also keep their 1.4 controls
inside the new settings pages. Choosing "No estimate" on a work item still does
not clear an estimate that is already set, as in `0.3.0`; this is fixed when
the work item screens move. In light mode, the General page of a project's
settings shows the name of a project without a cover image in white on a white
background, and the Hangar logo on the sign-in and sign-up pages has little
contrast against the page. Invitations sent before this release have no
recorded sender and stay with admins, as described above. The recorded upstream base stays Plane 1.4.0 with
the 1.4.3 changes backported. Page history starts with `0.4.0-rc.2`; edits made
before that have no versions. A mention keeps the mentioned user's id in the
stored text of a description or comment, so a visitor can tell that some
account was mentioned, but nothing on the board turns the id into a name.
Scripts up to `0.3.0` cannot detect that they are out of date, as described
above. On Kubernetes this release is qualified for evaluation on AMD64 only:
the production profile has still not completed qualification, so do not run
the chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that adds it if you
need it.

**Rolling back to `0.3.0`** needs no schema change and no change to the Helm
values: only the images change. Migration `0025` only added a configuration
row, which `0.3.0` does not read; leave it in place. `0.3.0` does not know the
migration and starts normally with it recorded, and an upgrade again later
keeps the value the row holds. Rolling back brings back the previous look of
the published boards and the whole web app on its previous design tokens and
components, a public board API that names every project member and assignee,
the lost first reaction, and workspace members who can invite people and
change or withdraw any pending invitation, whatever the switch says. It also
brings back the worker's log of task arguments, with the reset tokens, codes
and join tokens in it, and the invitation e-mail task that erases an
invitation's sender. `0.3.0`
records no page versions; those recorded since `0.4.0-rc.2` stay in the
database and stay readable in the history panel, but no new ones are added. The
release check in this release's script never refuses an older release, so it
does not stand in the way of a rollback. Rolling back to `0.4.0-rc.3`,
`0.4.0-rc.2` or `0.4.0-rc.1` is not supported, because they are superseded.
