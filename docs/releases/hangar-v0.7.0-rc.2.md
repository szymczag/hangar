## Security and privacy

> [!NOTE]
> **Changes since `0.7.0-rc.1`.** These notes cover everything `0.7.0`
> brings compared with `0.6.0`. The second candidate adds:
>
> - the live server's request logs no longer carry cookies, credential
>   headers or query strings, and its log entries are scrubbed of credentials
>   (first item below; read the advice on older logs);
> - the PDF export draws emoji typed or picked in the editor, and keeps a link
>   clickable only for `http`, `https`, `mailto` and `tel` addresses; the
>   editor's Markdown serializer writes an emoji's name only when it is a plain
>   shortcode;
> - the full-screen image viewer takes the keyboard again, so `+` and `-` no
>   longer replace the selected image, and the callout emoji search keeps
>   focus;
> - a correction: the `0.7.0-rc.1` notes said that every refused upload gets
>   the same 404 as a missing work item. The work item's attachment routes
>   answer a restricted guest with 403 instead, as the upload item below
>   describes.
>
> Items that are new in this candidate say so.

**The live server's request logs no longer contain cookies, credential
headers or query strings.** New in this candidate. Up to and including
`0.7.0-rc.1`, the live server wrote one log line per HTTP request with that
request's full headers and its query string. The lines therefore held the
browser's session cookie, other credential headers, among them the secret key
the API sends with its calls to the live server, and any token passed in a
query string. The request log line now records an allowlist only: the method,
the path without its query string or fragment, the HTTP version, the status,
the response time, and the `user-agent`, `content-type`, `content-length` and
`x-request-id` headers when they are present. Response headers and bodies are
not logged.

- Every log entry the live server writes now passes through a shared
  redaction step before it is written. It replaces credentials with
  `[REDACTED]` wherever they appear in the entry, in fields named after a
  cookie, token, secret, password or credential header at any depth, and in
  text such as header lines, cookie strings, authorization values, signed URL
  parameters and passwords in URLs. Logged objects themselves are never
  changed.
- The PDF export's own logs used to go straight to the console, outside the
  shared logger. They now go through it, as JSON, and are redacted the same
  way.

> [!IMPORTANT]
> **Logs written before the upgrade are not rewritten.** Treat the live
> server's logs from every earlier release as sensitive, and every copy a log
> shipper or backup has taken of them: rotate or delete them, and restrict who
> can read what you keep. On Compose and Swarm they are the Docker logs of the
> `live` service, in the all-in-one image `/app/logs/access/live.log` and
> `/app/logs/error/live.err.log`, and on Kubernetes the logs of the `live`
> pods. If those logs may have been readable by someone other than your
> operators, consider invalidating the sessions they could contain. Sessions
> are kept in the database's `sessions` table, and deleting its rows signs
> every user out of the web app, Spaces and God Mode; they then sign in again.
> In that case also consider changing `LIVE_SERVER_SECRET_KEY`, which the
> `api` and `live` services must share, and restarting both.

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
  without the address. A relative link (`/path`, `#anchor`) keeps working in
  the editor.
- If your workspaces rely on links to other schemes, find them before you
  upgrade and replace them with an `https://` address, or keep the address as
  plain text. Links typed in this release must use one of the four schemes.
- A page's PDF export applies the same allowlist, as the PDF export item below
  describes, and also prints a relative link as plain text. New in this
  candidate.

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
preview still closes on Escape and on a click outside it.

**The PDF export checks what it is asked for and what it prints, and draws
emoji from a bundled font.** A page's PDF export runs in the live server:

- **Request.** The live server took the workspace slug, page id and project id
  of an export request and put them into the paths of the requests it makes to
  the API, with the exporting user's own session, without checking them, so a
  crafted request could point those calls at another API path. Page and project
  ids must now be UUIDs, and a slug is refused if it contains `/`, `\`, `?`,
  `#`, `%`, a control character or a lone surrogate, or is `.` or `..`; such a
  request is answered with 400 before any API call. All three values are also
  encoded into every path the server builds. Workspaces whose slugs contain
  dots, which some older workspaces have, can still export.
- **Links.** New in this candidate. A link in the page becomes a clickable
  link in the PDF only when its address is an `http`, `https`, `mailto` or
  `tel` URL. Any other address, including a relative one, which a PDF viewer
  would resolve against the file's own location, and a link without an
  address, is printed as plain text, without the link style. Up to and
  including `0.7.0-rc.1`, the export turned every link's address into a
  clickable link in the PDF, whatever its scheme.
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
- **Emoji names.** New in this candidate. An emoji typed or picked in the
  editor is stored as its name, which is page content too. The export looks the
  name up in the editor's bundled emoji set, without any network access, and
  draws the emoji only when the result is exactly one emoji. A name the set
  does not know prints as `:name:` only when it is a plain shortcode (letters,
  digits, `_`, `+` and `-`, not a bare number, at most 64 characters), and
  otherwise prints nothing. The editor's Markdown serializer, in the web app,
  Spaces and the live server, follows the same rule: it used to write an
  unknown name into its output as it was stored, and now writes it only when it
  is such a plain shortcode, and otherwise leaves it out.
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
beta, framer-motion and Storybook: the lockfile loses their entries, and no
package is added or upgraded. The editor adds no new runtime dependency apart
from the in-repo `@makeplane/propel`. No inline script or style, `innerHTML`
or exception to the Content-Security-Policy is added, and the reviewed
inventories of script sinks are unchanged, except that Spaces loses one entry
(`eval` in lodash, which left its bundle with the old menus). The side-menu
drag and AI handles still draw their icons as SVG elements, never as markup,
and the image download and new-tab buttons keep `noopener,noreferrer`. This
removal changes no permissions.

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
  alignment as pressed, and the full-screen image viewer, which the next item
  describes. An empty image block has a "Choose image" button beside its drop
  zone.
- The code block's copy button, which also shows when the block has keyboard
  focus.
- The callout colour picker and logo picker.
- The icons of the editor toolbar in pages, stickies, work item descriptions
  and comments, and in the comment box on published boards.

What the controls do is unchanged, apart from the link rule above. Reload open
web app and Spaces tabs after the upgrade.

**The full-screen image viewer takes the keyboard, and the callout emoji
search keeps focus.** New in this candidate. In `0.7.0-rc.1`, in pages and
work item descriptions, the editor pulled keyboard focus back out of the
viewer as soon as it opened. Escape did not close it, and `+`, `=` and `-`
reached the editor instead, where they replaced the selected image with the
typed character until it was undone. Now:

- Opening the viewer puts focus on its close button, and focus stays inside
  the viewer while it is open, also after clicking one of its buttons.
- Escape closes the viewer and returns focus to the button that opened it.
- `+` and `=` zoom in, `-` zooms out and `0` resets the zoom to 100%. These
  keys no longer reach the editor or an enclosing dialog, such as a work
  item's peek view; shortcuts with Ctrl, Cmd or Alt, such as the browser's own
  zoom, still go to the browser.
- At the zoom limits the zoom buttons are marked unavailable but keep focus.
- The "View image in full screen" button opens the viewer with Enter or Space.

The same fault took focus from the callout logo picker's emoji search, so
typed search text went into the page. The search now keeps focus and shows
its focus ring.

**A new comment takes a pasted or dropped image.** Pasting or dropping an
image into a work item comment that was not saved yet failed with a 400, and
so did copy-pasting an image that is already on the page into it, because the
comment had no id for the image to belong to. This happened in the web app on
work items and intake items. The image is now held on the work item until the
comment is saved, and is read under that work item's visibility from the
first request; when the comment is created, it is bound to that comment.
Binding is restricted, and the rules apply both in the web app and on
published boards:

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

These rules are checked on the general asset routes, the v2 project asset
upload, binding and duplication routes
(`/assets/v2/workspaces/<slug>/projects/<id>/…` and
`…/duplicate-assets/<id>/`) and the legacy `/file-assets/` upload, and on the
board's own. A request that is refused there gets the same 404 as a missing
comment or work item. An empty or malformed identifier is still
refused with a 400.

**Uploaded files follow the work item's visibility, and a published board
serves only the images it shows.** Every way of uploading a file to a work
item applies the same rule: an attachment, a description image or a comment
image is attached only to a work item the uploader can see, and a restricted
guest attaches files only to work items they created. Deleting, restoring,
completing or moving a file that belongs to a work item needs the same
visibility, so a restricted guest changes no file on a work item they cannot
see. What a refused request gets depends on the route:

- On the general asset routes, those under `/assets/v2/workspaces/<slug>/`
  for upload, completion, deletion, restore, duplication and bulk binding, and
  the legacy `/file-assets/` routes, a work item hidden from the caller gets
  the same 404 as a missing one, and so does a file on it.
- On the work item's own attachment routes, `…/issues/<id>/attachments/` and
  the legacy `…/issues/<id>/issue-attachments/`, a restricted guest gets 403
  for a work item they did not create, as opening that work item itself
  already answers. They get the same 403 for an id that does not exist, so the
  answer does not tell which work items exist. **The `0.7.0-rc.1` notes were
  inaccurate here**: they said that every route answers a hidden work item
  with 404. The behaviour has not changed since `0.7.0-rc.1`; only its
  description has.

A published board serves, to visitors without a session, only the images it
shows:

- the description images of the work items it lists;
- the images in its external comments, when comments are enabled on the
  board.

An image uploaded on the board for a comment that has not been saved yet is
visible only to its uploader until the comment is saved. Some older images may
no longer load on a published board; Known limitations below lists them.

**Pressing Escape in the emoji suggestions closes them.** Typing `:` and a
name opens the emoji list; pressing Escape there threw an error instead of
closing it. It now closes the list and keeps what you typed.

**A page's PDF export prints emoji, callout emoji and mentions.** Emoji in a
page's text, headings, links, code and title used to come out as broken
characters, a callout's emoji was printed as its decimal code points (such as
`128161`), and a user mention as `@user_mention`. The export now draws emoji
from the bundled font, a callout with an emoji shows that emoji, and a mention
shows the user's display name. An emoji typed or picked in the editor, which
the page stores as an emoji element, now prints too, in text, headings and
tables, with the formatting around it; up to and including `0.7.0-rc.1` it was
left out of the PDF (new in this candidate). An emoji whose name the editor's
set does not know prints as `:name:`. A removed member's mention still shows
their name. A mention that cannot be resolved prints `@user`. The font is
monochrome, so skin tones are not shown: `👍🏽` prints as 👍. Links are
clickable in the PDF only for `http`, `https`, `mailto` and `tel` addresses;
the others print as plain text.

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

**No migration and no chart change.** This release adds no database or license
migration compared with `0.6.0` or `0.7.0-rc.1`, and the migrations lockfile
is unchanged. The Helm chart's templates, values and Secrets do not change.
The Compose and Swarm deployment contract does not change either:
`variables.env` is the same, and the published `docker-compose.yml` keeps its
services, settings and variables. The file itself does change, as it does in
every release: its header names `v0.7.0-rc.2`, and it pins the Hangar images
to this release's digests. Each release builds all seven Hangar images (`web`,
`admin`, `space`, `live`, `api`, `proxy` and the all-in-one `aio`) afresh, with
the release's version and refreshed Alpine packages, so every image digest
changes. Of the application code, compared with `0.6.0`:

- `web` and `space` carry the editor's new design, the link rule, the link
  hover fix, the emoji suggestion fix, the image viewer's keyboard handling and
  the emoji name rule of the Markdown serializer, and `web` also drops two
  unused libraries;
- `live` carries the PDF export changes, the force-close fix, the editor's
  link rule and emoji name rule, and the request log allowlist and log
  redaction, and grows by about 2 MB for the emoji font;
- `api` carries the comment image upload and binding rules, the upload rules
  that follow the work item's visibility and the published board's image
  rules, and its visual test seed command adds a page for the editor's
  screenshot tests and still refuses to run unless `HANGAR_VISUAL_FIXTURES=1`
  is set (the Celery workers, the scheduler and the migrator run the `api`
  image);
- the all-in-one image bundles them all;
- the `admin` code is unchanged, and its built stylesheet only loses utility
  classes that nothing uses any more; the `proxy` code is unchanged.

Compared with `0.7.0-rc.1`, only `web`, `space` and `live` carry code changes,
the ones marked new in this candidate above; the `api`, `admin` and `proxy`
code is unchanged. `setup.sh` and `swarm.sh` are unchanged since `0.6.0`,
apart from the release each names (`SCRIPT_RELEASE`), which the release
workflow writes into them. The in-app release notes in the web app name this
release.

Upgrade from `0.6.0` or `0.7.0-rc.1`. This is a release candidate, so the
installers do not pick it on their own, and the `0.6.0` script refuses a newer
release than its own. On Compose and Swarm:

1. Let the script replace itself:
   `HANGAR_RELEASE=v0.7.0-rc.2 ./setup.sh update-script`. It downloads and
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
3. Run `HANGAR_RELEASE=v0.7.0-rc.2 ./setup.sh upgrade`, as the owner of
   `plane-app/` or as root.
4. On Compose, the upgrade leaves every service stopped. It ends with
   `PLEASE VALIDATE AND START SERVICES` and the command that starts them:
   check `plane-app/plane.env`, then run `./setup.sh start`. Hangar stays down
   until you do. On Swarm, the upgrade redeploys the stack itself.
5. Rotate or delete the live server's logs written before the upgrade, and
   decide about sessions, as the first item of these notes describes.
6. For later releases, run `HANGAR_RELEASE=<release> ./setup.sh update-script`
   (or plain `./setup.sh update-script` for the latest stable release) before
   `./setup.sh upgrade`. If you skip it, the upgrade refuses and tells you what
   to run.

Use the `v0.7.0-rc.2` all-in-one image, or run `helm upgrade` with
`--version 0.7.0-rc.2` on Kubernetes. Neither needs a further step for the
upgrade itself; deal with the live server's logs as in step 5. Reload open web
app and Spaces tabs after the upgrade. Upgrading from a release older than
`0.6.0`, including `0.6.0-rc.2`, also brings what the
[`0.6.0` notes](hangar-v0.6.0.md) and the releases before it describe; read
them first. In particular, the `0.3.0` script cannot replace itself and must be
replaced by hand as the `0.4.0` notes show.

Product version is `v0.7.0-rc.2`, Git tag `hangar-v0.7.0-rc.2`, Helm chart
version `0.7.0-rc.2`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.7.0-rc.2`.

## Known limitations and rollback

This is the second release candidate for `0.7.0`. `0.6.0` stays the current
stable release, and the installers keep choosing it unless you name this
release. `0.7.0-rc.1` is superseded by this candidate: do not install it, and
upgrade an installation on it to `0.7.0-rc.2`.

Links with a scheme other than `http`, `https`, `mailto` or `tel` lose their
link when their content is next converted, as the link item above describes.
This is intended. Content that was saved without the link on this release
keeps the text without it, also after a rollback.

God Mode, the published boards, the whole web app and now the editor have the
new design. Upstream's restyled to-do checkbox is not taken yet, so to-do lists
keep their current checkboxes. The capacity screens stay in English, as
before. The web app's `custom` theme gets the light treatment of the Hangar
logo, which may not suit a dark custom palette. The recorded upstream base
stays Plane 1.4.0 with the 1.4.3 changes backported.

- Some older images may no longer load on a published board, because the
  board now serves only the images it shows: a description image that was
  never bound to a work item, an image pasted from one work item into another,
  and a comment image that was copied into another user's comment. They still
  load in the app for members who may see them.
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
- Live server logs written before the upgrade keep whatever they recorded, as
  the first item above describes.
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
does not come back. Rolling back brings back the editor's Plane 1.4 controls,
links with any scheme that parses, the inline handler attributes and Trusted
Types reports on link hover, the error on Escape in the emoji suggestions, the
400 when a new comment takes an image, the looser rules for binding images to
comments, the unchecked export request, the PDF export that prints emoji as
broken characters, callout emoji as code points and mentions as
`@user_mention`, leaves out emoji typed in the editor and makes every link
clickable, the callout value that can fail the export, the Markdown serializer
that writes an unknown emoji name unchecked, and the unhandled rejection and
"still in memory" errors in the live server's log when a page is too large to
save. It also brings back the live server's request log with full request
headers, cookies included, and query strings, so its logs become sensitive
again. The upload and published-board image rules of this release do not
apply there. The release check in this release's script never refuses an older
release, so it does not stand in the way of a rollback. Rolling back to
`0.7.0-rc.1` is not supported, because it is superseded.
