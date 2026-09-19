# Content-Security-Policy

The web, admin and space frontends send a Content-Security-Policy of their own.
It is part of the application, not of the reverse proxy in front of it: the
policy describes the frontends (where their scripts come from, what they inline,
which origins they talk to), so it is kept in `packages/csp` next to them and
changes in the same commit as the code it describes. Every installation built
from this repository gets it.

## Current status: enforced

The policy is **enforced** (`Content-Security-Policy`) and violations are
reported to `/api/csp-report/`, logged by the API as
`Content-Security-Policy violation`. `HANGAR_CSP_REPORT_ONLY=true`
(`contentSecurityPolicy.reportOnly: true`) sends it report-only instead, for a
deployment that wants to watch its reports before it blocks anything, for
example after adding an origin.

What it has been verified against, in Chromium with the policy enforced (see
"Verification" below): every screen of the visual suite, web and console;
signing in with a password on the web app, the console and a published board;
the rich-text editor with every formatting feature, markdown and hostile
pastes; comments; stickies; pages edited through live; the PDF export; a
published board read without an account; a screenshot pasted into a
description and one attached to a work item, both stored and shown from this
instance. The nginx images were checked with a read-only root filesystem.

**Images are only this instance's own**: its bundle, uploads in object
storage, and `blob:`/`data:` URLs made in the page. An image a description
points at on another host is not loaded, profile pictures from identity
providers are copied to object storage, and covers are chosen from the bundled
set or uploaded. `python manage.py localize_external_images` (report first,
then `--apply`) copies or clears profile pictures, covers and logos stored as
URLs on other hosts before this rule existed.

## What the policy allows

No directive contains `'unsafe-inline'`, `'unsafe-eval'` or `'wasm-unsafe-eval'`.

| Directive                                                                        | Sources                                                                                  | Why                                                                                                                                   |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `script-src`                                                                     | `'self'` plus a hash (web, admin) or a per-request nonce (space) for each inline script  | React Router inlines its context and module loader; next-themes inlines its anti-flash script                                         |
| `script-src-attr`                                                                | `'none'`                                                                                 | no inline event handlers, even if one ever got past the sanitizer                                                                     |
| `style-src`, `style-src-elem`                                                    | `'self'` plus the hash of Base UI's fixed scrollbar style                                | the stylesheets are bundled; TipTap's base CSS ships in `packages/editor/src/styles/prosemirror.css` instead of an injected `<style>` |
| `style-src-attr`                                                                 | `'none'`                                                                                 | the editor renders text colour, background and alignment as data attributes styled by its stylesheet, never as `style="…"`            |
| `img-src`                                                                        | `'self' blob: data:`, OAuth profile-picture hosts, Unsplash, plus object storage         | uploads, previews, avatars before they are copied to storage, cover images                                                            |
| `connect-src`                                                                    | `'self'`, `https://cdn.jsdelivr.net` (emoji picker data, JSON only), plus object storage | API, live WebSocket and uploads are same-origin by default                                                                            |
| `frame-ancestors`                                                                | `'none'` (web, admin); `'self'` or the configured list (space)                           | a published board can be embedded where the operator allows it                                                                        |
| `object-src`, `frame-src`                                                        | `'none'`                                                                                 |                                                                                                                                       |
| `form-action`, `base-uri`, `worker-src`, `manifest-src`, `font-src`, `media-src` | `'self'`                                                                                 |                                                                                                                                       |

Page export to PDF is rendered by the live server (`POST /live/pdf-export/`).
The browser no longer runs the PDF layout engine, which is WebAssembly and would
have required `'wasm-unsafe-eval'`.

## How it is produced

- **web, admin (static single-page builds):** `react-router build` is followed by
  `hangar-csp-nginx`, which hashes every inline `<script>` in the built
  `index.html` and writes `build/csp/security-headers.conf.template`. The image
  copies it to `/etc/nginx/templates/`. At start-up
  `/docker-entrypoint.d/15-hangar-csp.envsh` fills in the runtime origins and the
  nginx image renders the file into `/tmp/nginx-conf.d/` (the only writable path
  on a read-only root filesystem). `nginx.conf` includes it in every block that
  sets headers, because nginx does not inherit `add_header` into a block that
  has its own.
- **space (server-rendered):** `apps/space/app/entry.server.tsx` generates a nonce
  per request, passes it to React Router and next-themes, and sets the header.

A build whose `index.html` has no inline scripts fails, because that is not the
output the generator was written for.

## Configuration

All variables are optional.

| Variable                       | Default            | Meaning                                                                                                                                          |
| ------------------------------ | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `HANGAR_CSP_REPORT_ONLY`       | `false`            | Send `Content-Security-Policy-Report-Only` instead of enforcing.                                                                                 |
| `HANGAR_CSP_REPORT_URI`        | `/api/csp-report/` | Where browsers send violation reports. The API logs them under `plane.security.csp`, rate-limited per client. Empty disables reporting.          |
| `HANGAR_CSP_IMG_SRC`           | –                  | Extra image origins, space separated: object storage on another origin. Images are this instance's own; nothing else belongs here.               |
| `HANGAR_CSP_CONNECT_SRC`       | –                  | Extra origins the browser connects to: object storage on another origin, a separate API or live origin.                                          |
| `HANGAR_CSP_MEDIA_SRC`         | –                  | Extra media origins, normally object storage.                                                                                                    |
| `HANGAR_CSP_FRAME_SRC`         | `'none'`           | Origins that may be framed inside the application, such as a changelog page.                                                                     |
| `HANGAR_CSP_FORM_ACTION`       | –                  | Extra form targets, for an API on another origin.                                                                                                |
| `HANGAR_SPACE_FRAME_ANCESTORS` | `'self'`           | space only: who may embed a published board.                                                                                                     |
| `HANGAR_CSP_TRUSTED_TYPES`     | `report`           | `report` sends the Trusted Types policy below report-only; `enforce` enforces it and makes the pages' default policy sanitize; `off` removes it. |

The Helm chart sets these from `contentSecurityPolicy.*` in `values.yaml` and adds
the object-storage origin itself. With Caddy (`apps/proxy/Caddyfile.ce`)
everything, object storage included, is same-origin and nothing needs to be set.

A reverse proxy in front of Hangar should not add a Content-Security-Policy of
its own. A browser enforces every policy it receives, so a second one can only
narrow this one or conflict with it.

## Trusted Types measurement

Next to the policy above, every document response carries a second policy whose
mode is `HANGAR_CSP_TRUSTED_TYPES`, whatever `HANGAR_CSP_REPORT_ONLY` says. By
default it is report-only:

```
Content-Security-Policy-Report-Only: require-trusted-types-for 'script'; trusted-types hangar-inert default dompurify; report-uri /api/csp-report/
```

It is phase 0 of [trusted-types-plan.md](trusted-types-plan.md). The browser
reports each place where a plain string reaches a DOM sink that Trusted Types
would guard (`innerHTML`, `DOMParser`, script text …), and each attempt to
create a policy other than the three named, but blocks nothing and changes no behaviour. The API logs the
reports with the sink in `script-sample` (for example
`Element innerHTML|<svg xmlns=…`) and the location in `source-file`,
`line-number` and `column-number`. Together they are the inventory that the
next phases replace sink by sink.

The frontends also install Trusted Types policies (`@plane/csp/trusted-types`).
With them in place, library code no longer triggers the browser's reports;
instead the `default` policy observes each HTML string passing through it,
returns it unchanged, and reports only the ones DOMPurify would have changed.
Those arrive in the same log with `effective-directive` set to
`trusted-types-default-policy`, `violated-directive` to `html-would-change`,
`script` or `script-url`, and the part that would change in `script-sample`.
An ordinary editing session produces none.

`HANGAR_CSP_TRUSTED_TYPES=off` (`contentSecurityPolicy.trustedTypes: off`)
removes the header, for example if the report volume is unwelcome. Reports
share the per-client rate limit of the report endpoint.

`HANGAR_CSP_TRUSTED_TYPES=enforce` (`contentSecurityPolicy.trustedTypes:
enforce`) sends the same policy as `Content-Security-Policy`, so a plain string
reaching a DOM sink is refused. The page learns the mode from
`<meta name="hangar-trusted-types">` in its head, which nginx rewrites for web
and admin and space renders per request. The `default` policy then sanitizes
instead of observing: HTML reaches the sink as DOMPurify returns it (reported as
`html-changed` with `disposition: enforce` when that differs), and script text
and cross-origin script URLs are refused. It is opt-in: turn it on after a
release cycle in which the observations show nothing legitimate would change,
first on a staging instance. An unrecognised value means `report`.

Both modes are exercised with the policy enforced by the security suite in
`apps/visual-tests/security` (`pnpm vr`): the editor, pastes, comments,
stickies, pages edited through live, the PDF export, a published board and the
instance console.

## Rolling out

1. Deploy with the defaults. The policy is enforced; violations appear in the
   API log as `Content-Security-Policy violation`.
2. If a report names a legitimate origin (object storage, a separate API or
   live origin), add it through the variables above. If it names inline code,
   the fix belongs in the frontend.
3. To watch reports without blocking, set `HANGAR_CSP_REPORT_ONLY=true`
   (`contentSecurityPolicy.reportOnly: true`) and remove it again once the
   reports are explained.

### What enforcing can break, and what to set

Each of these was checked in a browser with the policy enforced (see
"Verification" below); the ones that depend on the deployment cannot be checked
for you:

- **Signing in with a password or a code.** Those forms post to the API, which
  answers with a redirect, and Chrome applies `form-action` to the redirect as
  well. The API must redirect to the origin the page is on: `WEB_URL` (or
  `APP_BASE_URL`), `ADMIN_BASE_URL` and `SPACE_BASE_URL` must match the
  origins users open. Otherwise the form is refused and the sign-in does
  nothing. An API on its own origin also needs `HANGAR_CSP_FORM_ACTION`.
  Signing in with Google, GitHub, GitLab, Gitea or OIDC starts with a
  navigation, which `form-action` does not govern.
- **Images from other hosts** are not loaded: `img-src` allows this instance
  and its object storage only. A profile picture from an identity provider is
  copied to object storage at sign-in and shows the initials until then; run
  `localize_external_images` once for pictures, covers and logos stored before.
  Uploads go through a presigned URL on the storage origin, which must be the
  page's own (Caddy) or in `HANGAR_CSP_CONNECT_SRC`/`HANGAR_CSP_IMG_SRC`
  (the Helm chart adds it).
- **A separate API, live or storage origin** belongs in
  `HANGAR_CSP_CONNECT_SRC` (and storage in `HANGAR_CSP_IMG_SRC` and
  `HANGAR_CSP_MEDIA_SRC`). The Helm chart does this for object storage.
- **Framing.** The web app and the console cannot be framed; a published
  board only by the instance itself unless `HANGAR_SPACE_FRAME_ANCESTORS` says
  otherwise.
- **A proxy that adds its own policy** narrows this one; remove it.

### Verification

`pnpm vr` serves the visual stack with each frontend's generated policy,
enforced, and fails any story in which a page reports a violation
(`apps/visual-tests/src/fixtures.ts`), so all of its screens are checked under
the policy production sends. The security suite in
`apps/visual-tests/security` adds what the stories do not reach: signing in
through the real forms of the web app, the console and a published board, the
editor and its pastes, pages through live, the PDF export, a published board,
uploading a screenshot, and an image on another host being refused.

## Related server-side measures

- The API sends `default-src 'none'; frame-ancestors 'none'` on its own
  responses (except the optional OpenAPI pages under `/api/schema/`).
- Object storage routed under the application origin by Caddy is served with
  `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox`, and
  attachment downloads are signed as `application/octet-stream`.
- Rich text is sanitized server-side with value checks for the attributes the
  editor turns into styling (`plane/utils/content_validator.py`), and the editor
  checks the same values when it renders, which also covers content that
  arrives through a collaborative session and never passes the API.
