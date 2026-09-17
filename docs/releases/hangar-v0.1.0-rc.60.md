## Security and privacy

**An account the identity provider owns can no longer give itself a Hangar password.**
Federated accounts are created with no local password, and the password-change endpoint
read that state as "there is no old password to confirm" rather than as "this account
does not use a password", so a request carrying only a new password was accepted. An
administrator pins a domain to SSO so the provider's controls are the way in — its
second factor, its lockout, its deprovisioning — and an account that quietly acquires a
local password is covered by none of them. Whether that password could then be used
depended on whether password sign-in was also enabled; the account should not be able to
create the option for itself either way. The refusal now mirrors the one already in
place for the email address, which the provider also owns.

**A comment filed through the API is sanitized on creation, not only on edit.**
The work item comment endpoint validated HTML when a comment was edited but not when it
was created, so `comment_html` posted to the create path reached the database with its
script tags intact. The web application parses stored HTML through the editor's schema
and drops what that schema does not know, which is why this was not visible there — but
the API hands the stored HTML to every other consumer, and an integration or a future
surface that renders it would have rendered the script. Creation now runs the same
allowlist as every other write path. Comments created before this release keep whatever
was stored; they are sanitized when next edited, and the editor has always been the
safe renderer.

**Markdown accepted through the API cannot smuggle markup past that allowlist.**
Work items, comments and intake now take a markdown field beside the HTML one. HTML
written inside markdown is escaped rather than rendered, and the rendered result passes
the same sanitizer as hand-written HTML, so markdown is not a second door with its own
policy. Verified against a 49-payload cross-site-scripting polyglot corpus through both
markdown and HTML on all three endpoints.

## Migrations and compatibility

Upgrade from `0.1.0-rc.58`. This release introduces no database migrations and no schema
change, so no migration Job is required beyond the ordinary release Job, and rollback is
not constrained by schema state.

`0.1.0-rc.59` carries the same changes as this release and is not installable. Its tag
was annotated but not signed, and the publication refused it before building anything:
no image, chart or GitHub release exists under that version, and none will, because a
pushed tag consumes its version rather than being moved. `rc.58` therefore remains the
previous retained release and the rollback target.

Product version is `v0.1.0-rc.60`, Git tag `hangar-v0.1.0-rc.60`, Helm chart version
`0.1.0-rc.60`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.0-rc.60`. No chart
resources, Secrets, storage, RBAC or NetworkPolicy contract changes are introduced.

**The Work Items list opens as a hierarchy, which changes what every user sees first.**
Sub-work items are hidden in the list layout by default, so the page opens on Epics and
work items without a parent, each expandable, and anything not filed under an Epic is
visible as such. Anyone who had never touched the **Show sub-work items** switch will
see a shorter list than they remember; turning that switch on in **Display** restores
the flat list, and the preference is stored per view as it always was. The board,
calendar, spreadsheet and timeline layouts are unchanged and still show every work item,
because hiding children there would change what a column or a row means.

Each work item identifier now carries its type's icon, and a **Parent** display
property is on by default, so list and board rows show which work item they belong to.
A project administrator can choose a type's icon in **Project settings → Work item
types**. Both are display properties and can be turned off per view.

Grouping the list or board by **Parent** or by **Epic** is new. Grouping by Epic places
an Epic and everything below it — including sub-work items of its Tasks — in one group,
which the server resolves per request; work items outside any Epic group under **None**.
These groupings always include sub-work items, so the **Show sub-work items** switch is
not offered while one is active. Dragging a work item between such groups changes its
parent, and a move the hierarchy rules refuse is reported with the server's own reason
rather than a generic failure.

The API additions are backwards compatible. `description_markdown` on work items and
intake, and `comment_markdown` on comments, are write-only fields accepted beside the
existing HTML fields; existing clients that send HTML are unaffected. Sending both the
markdown and the HTML field for the same content is rejected with 400 rather than
resolved silently. Markdown source is limited to 1 MB. The work item list endpoint
accepts `parent_id` and `epic_id` as `group_by` and `sub_group_by` values, and `parent`
and `epic` as filters for loading one group.

## Known limitations and rollback

Content written through the collaborative editor is persisted as a binary document that
the server-side HTML allowlist does not inspect. That is unchanged by this release and
is not addressed by it: the markdown and HTML write paths described above are sanitized,
the collaborative path is not. An operator evaluating this release should read that as
an open gap rather than as a property of descriptions in general.

Rollback to rc.58 — the previous retained release, rc.59 having never published —
restores the previous images. The list returns to showing every work
item, and the Parent property, the type icon and the Parent and Epic groupings
disappear from the interface; view preferences written by this release name groupings the
older build does not know and are ignored by it rather than failing. API clients that
adopted the markdown fields must send HTML again, because the older build rejects the
markdown fields as unknown. Content already stored is unaffected either way, since
markdown is rendered once at write time and what is stored is the same HTML any other
client would have sent. Because no migration is introduced, rollback has no schema
consequence.

The evaluation qualification boundary remains AMD64. The production profile remains
unsupported; this release does not claim a new live-cluster qualification. Publication
verifies the chart and images through the release workflow. Deployment and acceptance on
the user's environment remain a separate step.
