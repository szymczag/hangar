## Security and privacy

**A project's display name is no longer held to the identifier's character rule.**
`FORBIDDEN_IDENTIFIER_CHARS_PATTERN` forbids `- . ' & ( ) @ # % !` among others.
That is correct for an identifier, which becomes part of a work-item key and a
URL, and wrong for a display name, where those characters are ordinary. Applied
to the name it refused a great many real projects — "Pentest - Client X", "v1.0",
"Client's audit" — and it made project duplication impossible from the
interface, because the duplicate form prefills "&lt;source&gt; (Copy)" and
parentheses were forbidden, so the form's own default value was rejected by the
endpoint it submits to.

The name is now held to what one line of human text has to be: no characters in
Unicode category `Cc` or `Cf`, and a length cap. The identifier keeps the strict
pattern.

This is stricter than what it replaced in the way that matters. `\n` is not in
the old character class, and `.` does not match a newline, so the previous rule
permitted newlines, tabs and the bidirectional overrides in a project name while
forbidding apostrophes. A name carrying U+202E reorders the text around it in
every list it appears in, and no HTML escaping downstream helps, because the
characters are not markup. All of those are now refused.

Every sink a stored project name reaches was traced before the rule was relaxed:
there is no `dangerouslySetInnerHTML` in any source file; the published board's
server-rendered title and OpenGraph tags come from a returned data structure
that React escapes; the email templates autoescape every project variable and
the mailer rejects CR and LF in subjects; spreadsheet exports call
`sanitize_csv_row` at every writer call site, so a leading `=`, `+`, `-` or `@`
cannot begin a formula; and export filenames are built from the workspace slug
and a project UUID, never the name, so the newly permitted `.` cannot form a
path segment.

**Duplication failures now name the field that caused them.** The duplicate form
decoded only the shape the copy service raises and never the shape a serializer
rejection takes, so every validation failure fell through to a generic message
with nothing said about the offending field. Both shapes are decoded now.

## Migrations and compatibility

This release adds **no database migration**. The schema is unchanged in both
directions, and existing values, Secrets, storage, RBAC and NetworkPolicies
remain compatible.

The build identity dialog now shows the release highlights it carries. It never
did: the notes are generated from `docs/releases/hangar-v<version>.md`, so the
bundled value has no leading `v`, while `APP_VERSION` carries the tag's. The two
were compared exactly, so the comparison was permanently false and the dialog
reported "This build does not carry release notes" in every build, including the
one the notes were generated from. The leading `v` is now stripped from both
sides before comparing, and the highlights are still withheld on a genuine
version mismatch and on a development build, which is what that check is for.

Both fixes are application-level. Deploy the web and API images together; no
operator action is required, and rolling back needs no schema reversal.

## Known limitations and rollback

The four features introduced in `rc.41` were exercised against the released
images for this release: both of that release's migrations apply cleanly on
PostgreSQL, the maintenance notice endpoint answers anonymously with
`Cache-Control: no-store`, an active notice that has not been published to the
sign-in page is withheld from anonymous callers and served once published, the
workspace home-defaults and shared-link routes resolve behind authentication,
and the instance favicon is registered, raster-validated and reported in the
instance configuration.

What has still not been checked is how any of it looks. The maintenance bar's
appearance at narrow widths, the build identity dialog's layout, and the
workspace home-defaults settings page have not been viewed in a browser. Anyone
deploying this should look at those three surfaces.

Copying work items is not supported. Project duplication carries a project's
configuration and never its work items, so a copy contains no work items and
therefore no sub-items either.

`INSTANCE_SUPPORT_TEXT` still has no length cap and no character validation. The
validator introduced for the maintenance notice and adopted here for project
names is the one it should use.

To roll back, redeploy the previous image. No schema change accompanies this
release.
