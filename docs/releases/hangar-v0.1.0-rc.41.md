## Security and privacy

**A maintenance notice is private until an operator publishes it.** The endpoint the
maintenance bar reads has to answer anonymous callers, because the outage worth
announcing is the one that stops people signing in, and the sign-in page has no
session to offer. That makes it a disclosure surface. An anonymous caller is
therefore served a notice only when `show_on_sign_in` is set on it; by default a
notice reaches people with an account and nobody else. The God Mode form states the
consequence next to the toggle, because publishing to the sign-in page means
publishing to anyone who can reach it.

The public read is mounted at `/api/maintenance/` rather than under
`/api/instances/`. The session middleware selects the instance-admin cookie for any
request path containing "instances", so a signed-in reader arriving under that
prefix would carry no application session and be judged anonymous — silently
reducing every ordinary reader to the sign-in gate. Only the console endpoint keeps
the prefix, because it is the one that wants the admin cookie.

The notice response is never cached. `@cache_response` caches a serialized body, and
this body depends on whether the caller is authenticated, so a cached copy would
eventually be served to the wrong audience. The database row is cached for ten
seconds instead and the gate applied per request, with `Cache-Control: no-store` on
every response and a test that fails if the decorator is reintroduced.

**Notice text cannot carry invisible direction changes.** Every character in Unicode
category `Cc` or `Cf` is refused. That covers newlines and tabs in a single-line
strip, and more importantly the bidirectional overrides: U+202E in a banner rendered
above the entire application can make "maintenance at 22:00" read as something else
entirely, and escaping downstream does not help because the characters are not
markup. Messages are capped at 500 characters and carry no link field. The validator
is extracted so it can also cover `INSTANCE_SUPPORT_TEXT`, which has no cap today.

**Shared quick links are held to the same URL rules as personal ones.** A workspace
admin can now publish quick links to everyone in the workspace. Their URLs go through
Django's `URLValidator` with an explicit `http`/`https` allowlist after a bare host is
treated as `http` — the same shape upstream already applies to personal quick links,
which is what keeps a `javascript:` URL out of an href. Upstream's own validation was
reviewed as part of this work and is sound; no change was needed there.

**Editing shared links stays with administrators; hiding them does not.** Only a
workspace admin can add, edit or remove a shared link, and every such change reaches
every member's home page at once. Any member, including a guest, may hide one from
their own home page and bring it back. Hiding is deliberately not gated on the admin
role, because it is the only adjustment available to someone who does not own the
list.

**Home defaults never overwrite a choice somebody made, unless asked to.** New members
are seeded from the workspace defaults at the moment their membership is created.
Seeding uses `ignore_conflicts`, so a preference a person already holds always wins.
An administrator who wants to reach existing members must choose "apply to everyone
now", which is presented as irreversible; even then only the widgets named in the
defaults are rewritten, and any other preference survives.

## Migrations and compatibility

Two migrations are added, both additive: `ext.0015` creates the maintenance notice
table, and `ext.0016` creates the four workspace-defaults tables. No existing table
is altered and no data is rewritten.

The maintenance notice is stored in its own table rather than in
`InstanceConfiguration`. Its window needs real datetime columns so the server decides
whether a notice is active against its own clock, rather than the browser comparing
ISO strings in whichever timezone the reader is in. It also means the notice can be
set on a deployment where `SKIP_ENV_VAR` is false: the configuration endpoint returns
409 for every write there, which would have left config-as-code deployments unable to
announce an outage at all. There is deliberately no `MAINTENANCE_*` environment
variable, which would recreate that problem.

New members are seeded by a `post_save` receiver on `WorkspaceMember` rather than by
changing the home endpoint. By the time a browser first calls that endpoint the rows
exist, so its existing lazy seed finds them and leaves them alone. Every join path —
invitation, SSO auto-join, workspace creation — is covered, because all of them create
a workspace membership.

A workspace that sets no defaults is unaffected: nothing is seeded and the existing
behaviour applies unchanged. With no shared links and no maintenance notice, both
features render nothing.

`<main>` in the web app's root layout changes from `h-full` to `min-h-0 flex-1` so the
maintenance bar can occupy a sibling slot without pushing the application's bottom
edge past the viewport. With no notice showing, the bar renders nothing and `flex-1`
on a sole child is equivalent to `h-full`, so the layout is unchanged. A source-shape
test pins the classes.

The build identity dialog now reads its version from the instance API rather than the
bundled package version, which was upstream's `1.4.0` rather than this fork's. The
release highlights it shows are generated into the bundle at build time by
`pnpm generate:release-notes`, verified in CI by `pnpm check`, and rendered only when
the bundled version matches the running one. Opening the dialog makes no network
request.

A generator fix is included that is worth noting on its own: the generated translation
key union terminated its last member on a separate line, which failed `check:format`
on a clean tree. Because that failure cascades, type checking had not been running for
any package downstream of `@plane/i18n`.

## Known limitations and rollback

None of the four features in this release has been exercised in a browser. The
maintenance bar's two-tab propagation, its dismissal round trip and its appearance at
narrow widths; the workspace home-defaults settings page and the shared-link group on
the home widget; the redesigned build identity dialog; and the favicon replacement are
all covered by contract tests and reasoned against the design system, but not seen
rendered. Anyone deploying this should exercise those surfaces first.

Published boards (`apps/space`) do not show the maintenance notice. A notice there is
operational information handed to the public, and `show_on_sign_in` is not consent for
that surface; it would need its own toggle and its own polling decision.

Maintenance notice dismissal is stored per browser. Someone using a laptop and a phone
dismisses a notice twice, and clearing site data brings it back. The God Mode form says
so.

"Apply to everyone now" cannot be undone. Making it reversible would require snapshotting
every affected member's preferences, which roughly doubles the model work; it is presented
as a separate, explicitly-labelled choice rather than a checkbox for that reason.

The operator favicon replaces the built-in one through a `<link>` mutation after instance
configuration loads, so there is a brief flash of the built-in icon on a cold load. Legacy
`/favicon.ico` requests continue to hit the built-in asset. Only raster images are
accepted; `image/svg+xml` is refused by the upload validator.

To roll back, redeploy the previous image. Both migrations are additive, so an older
application version runs against this schema unchanged; the new tables are simply unread.
