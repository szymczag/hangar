# Content-Security-Policy

The web, admin and space frontends send a Content-Security-Policy of their own.
It is part of the application, not of the reverse proxy in front of it: the
policy describes the frontends (where their scripts come from, what they inline,
which origins they talk to), so it is kept in `packages/csp` next to them and
changes in the same commit as the code it describes. Every installation built
from this repository gets it.

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

| Variable                       | Default            | Meaning                                                                                                                                 |
| ------------------------------ | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `HANGAR_CSP_REPORT_ONLY`       | `true`             | Send `Content-Security-Policy-Report-Only` instead of enforcing. This release reports first; the next one enforces by default.          |
| `HANGAR_CSP_REPORT_URI`        | `/api/csp-report/` | Where browsers send violation reports. The API logs them under `plane.security.csp`, rate-limited per client. Empty disables reporting. |
| `HANGAR_CSP_IMG_SRC`           | –                  | Extra image origins, space separated: object storage on another origin, a self-hosted GitLab's avatars.                                 |
| `HANGAR_CSP_CONNECT_SRC`       | –                  | Extra origins the browser connects to: object storage on another origin, a separate API or live origin.                                 |
| `HANGAR_CSP_MEDIA_SRC`         | –                  | Extra media origins, normally object storage.                                                                                           |
| `HANGAR_CSP_FRAME_SRC`         | `'none'`           | Origins that may be framed inside the application, such as a changelog page.                                                            |
| `HANGAR_CSP_FORM_ACTION`       | –                  | Extra form targets, for an API on another origin.                                                                                       |
| `HANGAR_SPACE_FRAME_ANCESTORS` | `'self'`           | space only: who may embed a published board.                                                                                            |

The Helm chart sets these from `contentSecurityPolicy.*` in `values.yaml` and adds
the object-storage origin itself. With Caddy (`apps/proxy/Caddyfile.ce`)
everything, object storage included, is same-origin and nothing needs to be set.

A reverse proxy in front of Hangar should not add a Content-Security-Policy of
its own. A browser enforces every policy it receives, so a second one can only
narrow this one or conflict with it.

## Rolling out

1. Deploy with the defaults. The policy is report-only and violations appear in
   the API log as `Content-Security-Policy violation`.
2. If a report names a legitimate origin, add it through the variables above.
   If it names inline code, the fix belongs in the frontend.
3. Set `HANGAR_CSP_REPORT_ONLY=false` (`contentSecurityPolicy.reportOnly: false`)
   to enforce.

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
