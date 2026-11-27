## Security and privacy

**Behaviour change: editor links now accept only http, https, mailto and tel
addresses.** Up to and including `0.6.0`, the editor refused only
links that run script (`javascript:`, `data:`, `vbscript:`) and a few others
(`file:`, `about:`), and saved a link with any other scheme that the browser
could parse: `intent:`, `blob:`, `view-source:`, `ms-settings:`, `search-ms:`,
`ftp:` and the rest. Clicking such a link in the editor did nothing, but a
middle-click, a modifier-click or a read-only view handed the raw address to
the browser, which could open another application on the reader's machine.
The editor now keeps one allowlist for what it accepts, keeps and opens:
`http:`, `https:`, `mailto:` and `tel:`.

- The link field in the bubble menu and the link edit view refuse any other
  scheme and show an error, and automatic linking while you type no longer
  turns such an address into a link. Typing an address
  without a scheme still works: `example.com` and `localhost:3000` become
  `https://example.com` and `https://localhost:3000`.
- **Existing links with another scheme lose their link and keep their text.**
  This affects links already in descriptions, comments and pages, for example
  `ftp://files.example.com`, `slack://channel?id=…`, or a bare `host:port`
  such as `intranet:8080` that was saved without `https://`. The upgrade
  itself rewrites nothing and runs no migration: the stored content stays as
  it is until it is next converted. When the editor loads such a link from
  HTML, or someone pastes one, the text stays and the link is dropped; where a
  page still holds the link in its collaborative state, it is shown with an
  empty address and opens nothing. Content saved after that keeps the text
  without the address. A relative link (`/path`, `#anchor`) keeps working.
- If your workspaces rely on links to other schemes, find them before you
  upgrade and replace them with an `https://` address, or keep the address as
  plain text. Links typed in this release must use one of the four schemes.

The editor in the web app, in Spaces and in the live server's document
conversion all use the same rule. Raw input that hides a scripting scheme
behind tabs, newlines or leading control characters is refused before it is
parsed, as it already was for the link mark, and the link's `target` and
`rel` stay fixed.

**Hovering a link no longer writes inline event handlers into the page.** When
the pointer rested on a link, the editor copied the link preview's event
handlers onto the `<a>` element as `onkeydown` and `onpointerdown` attributes.
The enforced Content-Security-Policy refused to run them, but every hover sent
a Trusted Types violation report. The handlers are no longer applied; the
preview still closes on Escape and on a click outside it. Upstream Plane
`1.5.0` has the same fault.

**The PDF export checks what it is asked for and what it prints, and fetches
nothing from outside.** A page's PDF export runs in the live server:

- **Request.** The live server took the workspace slug, page id and project id
  of an export request and put them into the paths of the requests it makes to
  the API, with the exporting user's own session, without checking them, so a
  crafted request could point those calls at another API path. Page and project
  ids must now be UUIDs, and a slug is refused if it contains `/`, `\`, `?`,
  `#`, `%`, a control character or a lone surrogate, or is `.` or `..`; such a
  request is answered with 400 before any API call. All three values are also
  encoded into every path the server builds. Workspaces whose slugs contain
  dots, which some older workspaces have, can still export.
- **Callout emoji.** A callout stores its emoji as page content that anyone who
  may edit the page controls. The export now decodes it only through the check
  the Markdown serializer has used since `0.6.0`: exactly one emoji, from plain
  decimal code points. Anything else draws the default lightbulb, and none of
  the stored text is printed. That check now also refuses a value longer than
  any real emoji (more than 16 parts or 128 characters) before it does any
  work: a value with some 200,000 parts used to pass and then fail the whole
  export, and the Markdown serializer in the web app, Spaces and the live
  server, with a stack overflow. A single code point stored as a number, as the
  editor's HTML parser leaves it, is read correctly instead of failing.
- **Mentions.** The export used to ask a mentions route that exists only in
  Plane's commercial API, got a 404 and printed `@user_mention`. It now reads
  the workspace member list, with the exporting user's own session and the
  API's existing role check, the same list the editor uses; a workspace guest
  gets the same reduced rows the web app already loads for them. The live
  server keeps only each member's id, display name and avatar address, and the
  PDF prints only the display names of users mentioned on a page the reader
  may open. No route, permission or API change.
- **Emoji font.** The `live` image now carries Noto Emoji, Google's monochrome
  emoji font, under the SIL Open Font License 1.1, with the licence beside it.
  The file is pinned by its SHA-256, which a test checks, and the image build
  fails if it is missing. The export reads it from disk; it does not use
  react-pdf's emoji image source, which would fetch an image per emoji from a
  CDN at export time.

**The legacy component libraries leave the code base.** The editor moves to
upstream's Propel components, described below, and the two Plane 1.4
component packages, `@plane/ui` and the old `@plane/propel`, are removed with
their Storybooks. With them go Headless UI, Popper, Blueprint, the Base UI
beta, framer-motion and Storybook: the lockfile only loses entries, and no
package is added or upgraded. The editor adds no new runtime dependency apart from the in-repo
`@makeplane/propel`. No inline script or style, `innerHTML` or exception to
the Content-Security-Policy is added, and the reviewed inventories of script
sinks are unchanged, except that Spaces loses one entry (`eval` in lodash,
which left its bundle with the old menus). The side-menu drag and AI handles
still draw their icons as SVG elements, never as markup, and the image
download and new-tab buttons keep `noopener,noreferrer`. Permissions are
unchanged.

## Migrations and compatibility

**The editor now uses the new upstream 1.5.0 design.** `0.6.0` moved every web
screen to the Propel components but left the editor's own controls on the
Plane 1.4 components. They now move to upstream Plane `v1.5.0`'s Propel
components, in the web app and in Spaces:

- The bubble menu: the block type, link and colour menus, the formatting and
  alignment buttons.
- The link preview and link edit popovers.
- The slash command, mention and emoji suggestion lists.
- The block menu behind a paragraph's drag handle.
- The table's column and row menus. Their handles are now buttons labelled
  "Column options" and "Row options" that you can reach and open with the
  keyboard; the colour section is a labelled group, open by default.
- The image toolbar and its alignment menu, which now shows the current
  alignment as pressed. The full-screen image viewer keeps focus inside it
  while it is open, answers `+`, `=`, `-` and Escape, and returns focus to the
  image when it closes. An empty image block has a "Choose image" button
  beside its drop zone.
- The code block's copy button, which also shows when the block has keyboard
  focus.
- The callout colour picker.
- The icons of the editor toolbar in pages, stickies, work item descriptions
  and comments, and in the comment box on published boards.

What the controls do is unchanged, apart from the link rule above. Reload open
web app and Spaces tabs after the upgrade.

**A new comment takes a pasted or dropped image.** Pasting or dropping an
image into a work item comment that was not saved yet failed with a 400, and
so did copy-pasting an image that is already on the page into it, because the
comment had no id for the image to belong to. This happened in the web app on
work items and intake items. The image is now held on the work item until the
comment is saved, and is read under that work item's visibility from the
first request; when the comment is created, it is bound to that comment.
Upstream Plane `1.5.0` accepts the upload but never binds the image to the new
comment. Binding is restricted, and the rules apply both in the web app and
on published boards:

- **Only the uploader may bind an image, and only to a comment they may edit
  on the same work item.** A comment's author, a project admin or a workspace
  admin who is a member of the project may edit it. An image that is pending
  on one work item, or already belongs to one comment, cannot be moved to
  another work item, project or comment, and nobody can claim someone else's
  pending image. One image in a request that breaks the rule binds nothing.
- **Uploading or duplicating an image into a saved comment needs the right to
  edit that comment and to see its work item.** Before, any member of the
  project could attach an image to any comment whose id they knew, including
  one on a work item hidden from them. The image could not be read back, but
  it was stored on that comment. A restricted guest's own older comment on a
  work item they can no longer see does not take new images; its text stays
  editable.
- **A published board can no longer move a user's images between comments.**
  Binding images to your own comment on a board accepts only images that are
  unbound, pending on that comment's work item, or already that comment's, and
  anchors them to the comment's work item, so who may read an image matches
  where it is shown.

A request that is refused gets the same 404 as a missing comment or work item.
An empty or malformed identifier is still refused with a 400.

**Pressing Escape in the emoji suggestions closes them.** Typing `:` and a
name opens the emoji list; pressing Escape there threw an error instead of
closing it. It now closes the list and keeps what you typed. Upstream Plane
`1.5.0` has the same fault.

**A page's PDF export prints emoji, callout emoji and mentions.** Emoji in a
page's text, headings, links, code and title used to come out as broken
characters, a callout's emoji was printed as its decimal code points (such as
`128161`), and a user mention as `@user_mention`. The export now draws emoji
from the bundled font, a callout with an emoji shows that emoji, and a mention
shows the user's display name. A removed member's mention still shows their
name. A mention that cannot be resolved prints `@user`. The font is
monochrome, so skin tones are not shown: `👍🏽` prints as 👍.

**A page too large to save no longer leaves errors in every live server's
log.** When the API refuses to store a page because it is too large
(`content_too_large`), the live server closes that page for everyone, as
before. Each live server then also logged
`[UNHANDLED_REJECTION] Invalid typed array length` and
`❌ [FORCE_CLOSE] Document still in memory!`. The first came from the
Hocuspocus Redis extension decoding the server's own admin command as a
document message; that channel is now left to the handler meant for it, and a
document message that cannot be decoded is logged with its channel and size
and dropped. The second was a false alarm: a page cannot be unloaded while its
own save is still running, so the force close now leaves the unload to the
end of that save, which already did it. Other pages keep syncing and saving.
Upstream Plane `1.5.0` has the same code.

**No migration and no chart change.** This release adds no database or license
migration compared with `0.6.0`, and the migrations lockfile is unchanged. The
Helm chart's templates, values and Secrets do not change. The Compose and
Swarm deployment contract does not change either: `variables.env` is the same,
and the published `docker-compose.yml` keeps its services, settings and
variables. The file itself does change, as it does in every release: its header
names `v0.7.0-rc.1`, and it pins the Hangar images to this release's digests.
Each release builds all seven Hangar images (`web`, `admin`, `space`, `live`,
`api`, `proxy` and the all-in-one `aio`) afresh, with the release's version and
refreshed Alpine packages, so every image digest changes. Of the application
code, `web` and `space` carry the editor's new design, the link rule, the link
hover and the emoji suggestion fix, and `web` also drops two unused libraries;
`live` carries the PDF export changes, the force-close fix and the editor's
link rule, and grows by about 2 MB for the emoji font; `api` carries the
comment image upload and binding rules, and its visual test seed command adds
a page for the editor's screenshot tests and still refuses to run unless
`HANGAR_VISUAL_FIXTURES=1` is set (the Celery workers, the scheduler and the
migrator run the `api` image); and the
all-in-one image bundles them all. The `admin` code is unchanged; its built
stylesheet only loses utility classes that nothing uses any more. The `proxy`
code is unchanged. `setup.sh` and `swarm.sh` are unchanged since `0.6.0`,
apart from the release each names (`SCRIPT_RELEASE`), which the release
workflow writes into them. The in-app release notes in the web app name this
release.

Upgrade from `0.6.0`. This is a release candidate, so the installers do not
pick it on their own, and the `0.6.0` script refuses a newer release than its
own. On Compose and Swarm:

1. Let the script replace itself:
   `HANGAR_RELEASE=v0.7.0-rc.1 ./setup.sh update-script`. It downloads and
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
3. Run `HANGAR_RELEASE=v0.7.0-rc.1 ./setup.sh upgrade`, as the owner of
   `plane-app/` or as root.
4. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES` and the command that starts them:
   check `plane-app/plane.env`, then run `./setup.sh start`. Hangar stays down
   until you do. On Swarm, the upgrade redeploys the stack itself.
5. For later releases, run `HANGAR_RELEASE=<release> ./setup.sh update-script`
   (or plain `./setup.sh update-script` for the latest stable release) before
   `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells you what
   to run.

Use the `v0.7.0-rc.1` all-in-one image, or run `helm upgrade` with
`--version 0.7.0-rc.1` on Kubernetes. Neither needs a further step. Reload
open web app and Spaces tabs after the upgrade. Upgrading from a release older
than `0.6.0`, including `0.6.0-rc.2`, also brings what the
[`0.6.0` notes](hangar-v0.6.0.md) and the releases before it describe; read
them first. In particular, the `0.3.0` script cannot replace itself and must be
replaced by hand as the `0.4.0` notes show.

Product version is `v0.7.0-rc.1`, Git tag `hangar-v0.7.0-rc.1`, Helm chart
version `0.7.0-rc.1`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.7.0-rc.1`.

## Known limitations and rollback

This is the first release candidate for `0.7.0`. `0.6.0` stays the current
stable release, and the installers keep choosing it unless you name this
release.

Links with a scheme other than `http`, `https`, `mailto` or `tel` lose their
link when their content is next converted, as the first item above describes.
This is intended. Content that was saved without the link on this release
keeps the text without it, also after a rollback.

God Mode, the published boards, the whole web app and now the editor have the
new design. Upstream's restyled to-do checkbox is not taken yet, so to-do lists
keep their current checkboxes. The capacity screens stay in English, as
before. The web app's `custom` theme gets the light treatment of the Hangar
logo, which may not suit a dark custom palette. The recorded upstream base
stays Plane 1.4.0 with the 1.4.3 changes backported.

- Pasting or dropping an image into the description in the create work item
  dialog, or in the intake create dialog, still fails with a 400, because the
  work item does not exist yet and there is nothing to hold the image on. Add
  the image after the work item is created. This is a follow-up.
- An image pasted into a comment that is never saved stays attached to its
  work item, readable under that work item's visibility, and is deleted with
  the work item. Nothing sweeps such images earlier.
- The PDF export's emoji are monochrome, without skin tones, and a character
  outside the basic plane that is not an emoji (some rare CJK characters, for
  example) prints as a missing glyph, as before.
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

The all-in-one image does not send `Strict-Transport-Security` itself; put it
behind a proxy that adds it if you need it.

**Rolling back to `0.6.0`** needs no schema change and no change to the Helm
values: only the images change. Everything created on this release stays
readable there. A link dropped from content that was saved on this release
does not come back. Rolling back brings
back the editor's Plane 1.4 controls, links with any scheme that parses, the
inline handler attributes and Trusted Types reports on link hover, the error
on Escape in the emoji suggestions, the 400 when a new comment takes an
image, the looser rules for binding images to comments, the unchecked export
request, the PDF
export that prints emoji as broken characters, callout emoji as code points
and mentions as `@user_mention`, the callout value that can fail the export,
and the unhandled rejection and "still in memory" errors in the live server's
log when a page is too large to save. The release check in this release's
script never refuses an older release, so it does not stand in the way of a
rollback.
