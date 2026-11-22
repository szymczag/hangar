## Security and privacy

**Published boards no longer reveal who is in the project.** Anyone with a
board's link can read its API (`/api/public/anchor/<anchor>/…`) without
signing in. Up to and including `0.3.0` that API named every project member,
as upstream Plane does by design: each work item carried `assignee_ids` and
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
  release, or of the one named in `HANGAR_RELEASE`, into a scratch folder beside
  the script. It verifies it as it verifies the deployment files (`SHA256SUMS`,
  and its Cosign signature when Cosign is installed), checks that it names that
  release, and renames it over the old script with mode `755` and the old
  owner. It never runs the new script, and a failed check leaves the old one as
  it was.

> [!IMPORTANT]
> **The protection starts with this release's script.** Scripts up to and
> including `0.3.0` do not know their own release and have no `update-script`
> action, so they cannot warn you. Replace your `setup.sh` (or `swarm.sh`) by
> hand once, as the
> [installation guide](../../deployments/cli/community/README.md#upgrading-hangar-version)
> describes and [Upgrade](#migrations-and-compatibility) below shows. After
> that, `./setup.sh update-script` replaces it for you and the script tells you
> when it is out of date.

**Spaces keeps its Content-Security-Policy on the new design and loads no
emoji data from a CDN.** Spaces, the server-rendered app that serves published
boards, keeps its per-request nonce policy. No hash, nonce source or
exception is added. The new components bring in Base UI; Spaces now hands it
the request's nonce, so the one script Base UI can write before the page
hydrates would carry it. No board page emits that script today. The emoji
picker behind the reaction button reads its data from this instance, under
`/spaces/emojibase/`, never from the public CDN that its library uses by
default and that the policy would refuse. A new security test opens the picker
on a published board without an account and fails on any request that leaves
the instance's origin.

## Migrations and compatibility

**The published boards move to the new upstream 1.5.0 design.** Spaces now
uses the Propel component library and the `@plane/blocks` components from
upstream Plane `v1.5.0`, as God Mode has since `0.3.0`: the sign-in forms,
filters, list and board layouts, property chips, the side panel with its
activity and comments, reactions and votes, the navigation bar and toasts. The
Hangar name and mark, the error page and the terms links stay Hangar's. The
sign-up form keeps Hangar's password rules: at least 15 characters and a strong
enough strength estimate. Upstream's new boards show every work-item property,
assignees included; **Hangar's boards still show only the key, state,
priority, labels and due date.** The side panel gains a labels row, and labels
were already on the cards. The web app keeps the Plane 1.4 design.

**Breaking change for clients of the public board API.** A script, integration
or embedded board that reads `/api/public/` must change if it uses any of:

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

Signed-in applications and the API-token API (`/api/v1/`) are unchanged, and so
are the board's metadata, states, labels, cycles and modules.

**No database migration and no chart change.** This release adds no database
or license migration compared with `0.3.0`, and the migrations lockfile is
unchanged. The Helm chart's templates, values and Secrets do not change, and
neither do the Compose and Swarm deployment files. The installer scripts
`setup.sh` and `swarm.sh` change as described above. The `space` image's
Dockerfile, server and headers do not change; the `api` image changes for the
public board API. The `web`, `admin` and `live` application code is
unchanged apart from shared helpers, which do not change their output. The
in-app release notes in the web app name this release.

Upgrade from `0.3.0`. This is a release candidate, so the installers do not
pick it on their own. On Compose and Swarm:

1. Replace the script by hand, because the `0.3.0` script cannot replace
   itself. Do not download the new script straight over the old one: fetch it
   with the release's `SHA256SUMS` and `SHA256SUMS.sigstore.json` into a folder
   of its own next to `plane-app/`, check it, and only then copy it into place:

   ```sh
   mkdir -p hangar-v0.4.0-rc.1 && cd hangar-v0.4.0-rc.1
   curl -fsSL -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.1/setup.sh \
     -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.1/SHA256SUMS \
     -O https://github.com/szymczag/hangar/releases/download/hangar-v0.4.0-rc.1/SHA256SUMS.sigstore.json
   cosign verify-blob --bundle SHA256SUMS.sigstore.json \
     --certificate-identity https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/hangar-v0.4.0-rc.1 \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS
   sha256sum --check --ignore-missing SHA256SUMS
   cd .. && cp hangar-v0.4.0-rc.1/setup.sh ./setup.sh && chmod 755 ./setup.sh
   ```

   On macOS use `shasum -a 256 --check --ignore-missing SHA256SUMS`. If either
   check fails, stop: your old script is untouched. On Swarm, download
   `swarm.sh` instead and copy `hangar-v0.4.0-rc.1/swarm.sh` over your
   `setup.sh`.
   [Upgrading Hangar Version](../../deployments/cli/community/README.md#upgrading-hangar-version)
   explains each command.

2. Run `HANGAR_RELEASE=v0.4.0-rc.1 ./setup.sh upgrade`, as the owner of
   `plane-app/` or as root.
3. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES`: check `plane-app/plane.env`, then run
   `./setup.sh start`. Hangar stays down until you do. On Swarm, the upgrade
   redeploys the stack itself.
4. For later releases, run `HANGAR_RELEASE=<release> ./setup.sh update-script`
   (or plain `./setup.sh update-script` for the latest stable release) before
   `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells you what
   to run.

Use the `v0.4.0-rc.1` all-in-one image, or run `helm upgrade` with
`--version 0.4.0-rc.1` on Kubernetes. Neither needs a further step.
Reload open published boards after the upgrade. Upgrading from a release older
than `0.3.0` also brings what the [`0.3.0` notes](hangar-v0.3.0.md) and the
releases before it describe; read them first. In particular, an upgrade from
`0.2.2` or older needs this release's script for the `plane.env` permission
fix as well.

Product version is `v0.4.0-rc.1`, Git tag `hangar-v0.4.0-rc.1`, Helm chart
version `0.4.0-rc.1`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.4.0-rc.1`.

## Known limitations and rollback

This is a release candidate for `0.4.0`. `0.3.0` stays the current stable
release, and the installers keep choosing it unless you name this release.

God Mode and the published boards have the new design; the web app keeps the
Plane 1.4 design until the redesign is adopted there too. The recorded upstream
base stays Plane 1.4.0 with the 1.4.3 changes backported. A mention keeps the
mentioned user's id in the stored text of a description or comment, so a
visitor can tell that some account was mentioned, but nothing on the board
turns the id into a name. Scripts up to `0.3.0` cannot detect that they are out
of date, as described above. On Kubernetes this release is qualified for
evaluation on AMD64 only: the production profile has still not completed
qualification, so do not run the chart in production yet. The all-in-one image
does not send `Strict-Transport-Security` itself; put it behind a proxy that
adds it if you need it.

**Rolling back to `0.3.0`** needs no schema change and no change to the Helm
values: only the images change. It brings back the previous look of the
published boards, and a public board API that names every project member and
assignee. The release check in this release's script never refuses an older
release, so it does not stand in the way of a rollback.
