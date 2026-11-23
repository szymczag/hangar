## Security and privacy

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
data, and still name nobody.** New in this candidate.
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

The web app's move to the new design tokens, described below, adds no inline
script or style and no exception to its Content-Security-Policy, and its
Trusted Types policies are still installed before anything renders. Both of
its emoji pickers read their data from this instance, never from a CDN.

## Migrations and compatibility

**Page version history is now recorded.** No Hangar release before this one
recorded it. Every page save started a background task that failed on a field
upstream Plane had renamed (`AttributeError: 'Page' object has no attribute
'description'`), and the task only logged the error, so the save itself
succeeded and the page's version history stayed empty. Upstream Plane `v1.5.0`
has the same bug. From this release on, saving a page records a version: a
user's saves within ten minutes update that user's latest version, and a page
keeps at most its 20 most recent versions. **Versions are recorded from this
release on, not for earlier edits**: history before the upgrade cannot be
recovered. The version history panel and its endpoints are unchanged and need
no migration. Anyone who can open a page can open its history, under the same
project and guest rules as the page itself, so text removed from a page stays
readable in its earlier versions until they age out.

**The web app loads the new upstream 1.5.0 design tokens.** This is the first
step in moving the web app to the Propel design that God Mode and the published
boards already use. The web app's stylesheet now carries Propel's colour,
typography and spacing tokens, and its components, which are unchanged, render
on them. Colours, font weights, line heights and letter-spacing shift slightly
across the whole web app: some light-mode greys are a little darker, accent,
danger and warning tints move by a step, regular text is slightly heavier,
body lines are a little taller and text a little wider, so lists and cards
grow by a few pixels. Menus still open above dialogs. The web app also waits
for its translations to load before it hydrates, as Spaces already does; a
failed translation load does not stop the app from starting.

**The first reaction on a published work item now saves.** New in this
candidate. On a work item nobody had reacted to, Spaces dropped the reaction
before it sent it: the board API answered `null` instead of an empty list for
`reaction_items` and `vote_items`, and Spaces failed on it. The API now
answers an empty list on the work item and on the board's lists, grouped or
not, and Spaces tolerates `null` from an older server. A failed vote or
reaction no longer leaves the work item showing rows it cannot read. Up to and
including `0.4.0-rc.1`, and on `0.3.0`, the first reaction on a work item was
lost.

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

New in this candidate, `vote_items` and `reaction_items` are an empty list
rather than `null` on a work item without votes or reactions, and the votes and
reactions lists return data, as described above. Signed-in applications and
the API-token API (`/api/v1/`) are unchanged, and so are the board's metadata,
states, labels, cycles and modules.

**No database migration and no chart change.** This release adds no database
or license migration compared with `0.3.0` or `0.4.0-rc.1`, and the migrations
lockfile is unchanged. The Helm chart's templates, values and Secrets do not
change, and neither do the Compose and Swarm deployment files. Compared with
`0.4.0-rc.1`, the `api` image changes for page versions and the board's votes
and reactions, the `space` image for the first reaction, and the `web` image
for the design tokens. The `admin` and `live` application code is unchanged.
`setup.sh` now prints the command that starts the services after an upgrade;
`swarm.sh` does not change. The in-app release notes in the web app name this
release.

Upgrade from `0.3.0` or `0.4.0-rc.1`. This is a release candidate, so the
installers do not pick it on their own. On Compose and Swarm:

1. Replace the script with this release's.
   - **From `0.4.0-rc.1`**, let the script replace itself:
     `HANGAR_RELEASE=v0.4.0-rc.2 ./setup.sh update-script`. It downloads and
     verifies the new script and changes nothing if a check fails.
   - **From `0.3.0`**, replace it by hand, because the `0.3.0` script cannot
     replace itself. Do not download the new script straight over the old one:
     fetch it with the release's `SHA256SUMS` and `SHA256SUMS.sigstore.json`
     into a folder of its own next to `plane-app/`, check it, and only then
     copy it into place:

     ```sh
     mkdir -p hangar-v0.4.0-rc.2 && cd hangar-v0.4.0-rc.2
     curl -fsSL -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.2/setup.sh \
       -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.2/SHA256SUMS \
       -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.2/SHA256SUMS.sigstore.json
     cosign verify-blob --bundle SHA256SUMS.sigstore.json \
       --certificate-identity https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/hangar-v0.4.0-rc.2 \
       --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS
     sha256sum --check --ignore-missing SHA256SUMS
     cd .. && cp hangar-v0.4.0-rc.2/setup.sh ./setup.sh && chmod 755 ./setup.sh
     ```

     On macOS use `shasum -a 256 --check --ignore-missing SHA256SUMS`. If
     either check fails, stop: your old script is untouched. On Swarm,
     download `swarm.sh` instead and copy `hangar-v0.4.0-rc.2/swarm.sh` over
     your `setup.sh`.
     [Upgrading Hangar Version](../../deployments/cli/community/README.md#upgrading-hangar-version)
     explains each command.

2. Run `HANGAR_RELEASE=v0.4.0-rc.2 ./setup.sh upgrade`, as the owner of
   `plane-app/` or as root.
3. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES` and, with this release's script, the
   command that starts them: check `plane-app/plane.env`, then run
   `./setup.sh start`. Hangar stays down until you do. On Swarm, the upgrade
   redeploys the stack itself.
4. For later releases, run `HANGAR_RELEASE=<release> ./setup.sh update-script`
   (or plain `./setup.sh update-script` for the latest stable release) before
   `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells you what
   to run.

Use the `v0.4.0-rc.2` all-in-one image, or run `helm upgrade` with
`--version 0.4.0-rc.2` on Kubernetes. Neither needs a further step.
Reload open web app tabs and published boards after the upgrade. Upgrading
from a release older than `0.3.0` also brings what the
[`0.3.0` notes](hangar-v0.3.0.md) and the releases before it describe; read
them first. In particular, an upgrade from `0.2.2` or older needs this
release's script for the `plane.env` permission fix as well.

Product version is `v0.4.0-rc.2`, Git tag `hangar-v0.4.0-rc.2`, Helm chart
version `0.4.0-rc.2`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.4.0-rc.2`.

## Known limitations and rollback

This is a release candidate for `0.4.0`. `0.3.0` stays the current stable
release, and the installers keep choosing it unless you name this release.
`0.4.0-rc.1` is superseded by this candidate: do not install it, and upgrade
an installation on it to `0.4.0-rc.2`.

God Mode and the published boards have the new design. The web app has the new
design tokens but keeps its Plane 1.4 components until they move in later
releases. The recorded upstream base stays Plane 1.4.0 with the 1.4.3 changes
backported. Page history starts with this release; edits made before the
upgrade have no versions. A mention keeps the mentioned user's id in the stored
text of a description or comment, so a visitor can tell that some account was
mentioned, but nothing on the board turns the id into a name. Scripts up to
`0.3.0` cannot detect that they are out of date, as described above. On
Kubernetes this release is qualified for evaluation on AMD64 only: the
production profile has still not completed qualification, so do not run the
chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that adds it if you
need it.

**Rolling back to `0.3.0`** needs no schema change and no change to the Helm
values: only the images change. It brings back the previous look of the
published boards and the web app's previous design tokens, a public board API
that names every project member and assignee, and the lost first reaction.
`0.3.0` records no page versions; those recorded on this release stay in the
database and stay readable in the history panel, but no new ones are added. The release check in this
release's script never refuses an older release, so it does not stand in the
way of a rollback. Rolling back to `0.4.0-rc.1` is not supported, because it is
superseded.
