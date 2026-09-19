# Trusted Types: implementation plan

Status: phases 0 (measurement), 1 (our own sinks), 2 (policies, observing)
and 3 (verification under enforcement) done; phase 4 not started. See "Trusted Types measurement" in
content-security-policy.md.
Measurements below come from the web build of
`fix/rich-text-sanitizer-and-csp` (a bundle scan with source maps, and a
Chromium session with `require-trusted-types-for 'script'` in report-only mode
while editing a work item).

## What it gives us

With Trusted Types required, every DOM sink that can turn a string into code
(`innerHTML`, `outerHTML`, `insertAdjacentHTML`, `DOMParser.parseFromString`,
`document.write`, `script.src`/`text`, `srcdoc`, `new Worker(url)` …) refuses a
plain string. It accepts only a `TrustedHTML` / `TrustedScript` /
`TrustedScriptURL` value, and those can only be produced by a _policy_ whose name
the Content-Security-Policy allows.

The DOM-XSS class stops being "every call site must remember to sanitize" and
becomes "the few policies must be right". The paste bug fixed in this branch
(`innerHTML` on a live-document element with clipboard content) would have been
a thrown `TypeError` in development instead of a script running in production.

It does not replace the server allowlist or the editor schema: it guards the DOM
sinks, not what React renders as text, not CSS, not URLs in `href`.

## Inventory (measured)

Every sink in the web bundle, grouped by who owns it. "Seen" means it fired in
the editor session.

| #   | Owner                                                | Where                                                                                                                                                       | Sink                                       | Input                                    | Seen   | Treatment                                                                      |
| --- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ---------------------------------------- | ------ | ------------------------------------------------------------------------------ |
| 1   | ours                                                 | `packages/editor/src/core/plugins/drag-handle.ts` (×2), `ai-handle.ts`                                                                                      | `innerHTML`                                | constant SVG                             | yes    | build the icon with DOM APIs (phase 1)                                         |
| 2   | ours                                                 | `packages/editor/src/core/extensions/table/plugins/insert-handlers/utils.ts` (×2)                                                                           | `innerHTML`                                | constant SVG                             | yes    | same                                                                           |
| 3   | ours                                                 | `packages/editor/src/core/helpers/paste-asset.ts`, `plugins/markdown-paste.ts`, `helpers/parser.ts`, `apps/web/core/hooks/use-parse-editor-content.ts` (×2) | `DOMParser.parseFromString`                | clipboard / stored HTML, parsed inert    | yes    | one `parseInertHTML()` helper on a named policy                                |
| 4   | ours                                                 | `apps/web/core/hooks/use-parse-editor-content.ts:80`                                                                                                        | `innerHTML` on an inert document's element | stored code-block HTML (export)          | no     | rewrite with DOM APIs (text + `<br>`)                                          |
| 5   | ProseMirror                                          | `prosemirror-view` `readHTML` (paste)                                                                                                                       | `innerHTML` in a detached document         | clipboard HTML                           | no\*   | already TT-aware: uses the `default` policy, or creates `ProseMirrorClipboard` |
| 6   | TipTap                                               | `@tiptap/core` `elementFromString` (setContent, insertContent)                                                                                              | `DOMParser.parseFromString`                | stored / inserted HTML                   | yes    | default policy (inert parse)                                                   |
| 7   | tiptap-markdown                                      | `elementFromString`, `formatBlock`, code-block `updateDOM`, paragraph trimming                                                                              | `DOMParser`, `innerHTML` on inert elements | markdown → HTML                          | yes    | default policy                                                                 |
| 8   | next-themes                                          | anti-flash `<script>` rendered by React with `dangerouslySetInnerHTML`                                                                                      | `innerHTML` (script)                       | constant built from the provider's props | yes    | default policy: exact-match allowlist                                          |
| 9   | @bprogress/core                                      | progress bar template                                                                                                                                       | `innerHTML`                                | constant template                        | yes    | default policy: exact-match allowlist                                          |
| 10  | React DOM                                            | `dangerouslySetInnerHTML`, script creation for hoisted resources                                                                                            | `innerHTML`, `script.text`                 | whatever the caller passes               | via #8 | nothing of ours uses it; covered by #8 and the default policy                  |
| 11  | element-resize-detector (stickies masonry)           | object/iframe resize sensor                                                                                                                                 | `innerHTML`                                | constant markup                          | no     | default policy: exact-match allowlist                                          |
| 12  | decode-named-character-reference (markdown renderer) | entity decoding                                                                                                                                             | `innerHTML` on a live element              | `&name;`, name from the parser           | no     | default policy: accept only `^&[A-Za-z0-9]+;$`                                 |
| 13  | highlight.js                                         | `highlightElement`                                                                                                                                          | `innerHTML`                                | —                                        | no     | not on our code path (lowlight is used); default policy rejects                |
| 14  | TipTap                                               | `createStyleTag`                                                                                                                                            | `innerHTML` (style)                        | —                                        | no     | disabled (`injectCSS: false`)                                                  |
| 15  | lodash, decimal.js                                   | `Function("return this")`                                                                                                                                   | eval                                       | —                                        | no     | never reached in browsers; already refused by `script-src`                     |

\* Paste went through `paste-asset.ts` (#3) in the session; ProseMirror's own
parser runs when the paste carries only `text/html`.

`jsx-dom`, React Router and React DOM carry sink code for features we do not
use (`dangerouslySetInnerHTML` on the server path, `jsx-dom` HTML props).
Enforcement is what tells us for certain: a sink we missed throws, and the
report names it.

## Design

### Policies

Created in one module, `packages/csp/src/trusted-types.ts`, and installed first
in each client entry (`apps/web/app/entry.client.tsx`,
`apps/admin/app/entry.client.tsx`, `apps/space/app/entry.client.tsx`), before any
other import runs. The policy objects are not exported. Callers get functions.

1. **`hangar-inert`** — `createHTML` returns its input unchanged. Used only
   inside `parseInertHTML(html): Document` (`DOMParser` into a document with no
   browsing context). Nothing parsed there runs. The risk is code that later
   moves those nodes into the page, which is why the function returns a
   `Document`, and every caller in our code feeds it to the editor schema or reads
   text from it.
2. **`hangar-icons`** — not needed after phase 1 replaces the constant-SVG
   `innerHTML` with DOM construction. Kept out of the design on purpose: a
   constant-string policy invites non-constant use.
3. **`default`** — the fallback the browser calls for library code that passes
   a plain string:
   - `createHTML(value, _type, sink)`:
     - exact match against a frozen set of known library constants (next-themes
       script for our provider options, bprogress template,
       element-resize-detector markup), or the entity pattern for
       decode-named-character-reference → return unchanged;
     - `sink === "DOMParser parseFromString"` (TipTap, tiptap-markdown, inert by
       construction) → `DOMPurify.sanitize(value, EDITOR_CONFIG)`;
     - anything else → `DOMPurify.sanitize(value, EDITOR_CONFIG)` and a report
       (`console.error` in development, a beacon to `/api/csp-report/` in
       production) naming the sink and the first 80 characters, so an unknown
       sink is visible without breaking the page.
   - `createScript` → only exact matches of the known inline scripts
     (next-themes); otherwise `null` (the sink throws).
   - `createScriptURL` → same-origin URLs only; otherwise `null`.

   `EDITOR_CONFIG` for DOMPurify keeps the editor's markup intact: `ADD_TAGS`
   `image-component`, `mention-component`, `issue-embed-component`; `ADD_ATTR` for
   the editor's data attributes and custom attributes; `FORBID_ATTR: ["style"]`;
   `ALLOWED_URI_REGEXP` for http(s), mailto, tel and relative URLs. It mirrors
   the server allowlist, and a test keeps the two lists in step, as the palette
   test does.

4. **`dompurify`** — the policy DOMPurify creates itself when asked for
   `RETURN_TRUSTED_TYPE`; allowed so the default policy can hand DOMPurify's
   result straight to the sink.
5. **`ProseMirrorClipboard`** — not allowed. With a `default` policy present,
   ProseMirror uses it (see #5), so the pass-through policy it would otherwise
   create is never needed, and refusing its name keeps it that way.

### Header

In `@plane/csp`, added to the same policy the frontends already send:

```
require-trusted-types-for 'script';
trusted-types hangar-inert default dompurify
```

No `'allow-duplicates'`: a second policy with one of these names is an error,
which is what should happen if anything tries to claim one.

### Browser support

Chromium-based browsers enforce Trusted Types. Where it is not supported, the
header directives are ignored and `window.trustedTypes` is absent. The module
then installs nothing and `parseInertHTML` passes strings as before, so code
behaves identically. The protection is Chromium-first, which is where most of
our users are.

## Phases

**Phase 0 — measure (half a day).** Add the two directives to the
report-only policy, in both the nginx template and space. Ship with the current
report-only rollout. Violations reach `/api/csp-report/` with a `sample` naming
the sink. This also covers screens the probe did not visit.

**Phase 1 — remove our own sinks. Done.**

- The constant-SVG `innerHTML` (#1, #2) is gone: `createSvgIcon` in
  `packages/editor/src/core/helpers/svg-icon.ts` builds the icons with
  `createElementNS`. The drag handle and both table insert buttons were
  compared against screenshots taken before the change: zero differing pixels.
- Every `DOMParser` of ours goes through `parseInertHTML` in `@plane/utils`
  (#3), now the only sink in our code.
- The export code-block conversion (#4) was in a function nothing called any
  more (the browser PDF renderer moved to the live server); the function was
  removed rather than rewritten.
- Instead of a lint rule (oxlint has none that matches an `innerHTML`
  assignment), `packages/csp/tests/dom-sinks.test.mjs` scans the sources and
  fails on any Trusted Types sink outside `parseInertHTML`.
- After it, an editor session reports only library sinks and
  `parseInertHTML`'s `DOMParser`.

**Phase 2 — policies. Done, in observe mode.**

- `@plane/csp/trusted-types` creates `hangar-inert` (used by `parseInertHTML`)
  and `default`; the three client entries install them before React renders.
  The header names `hangar-inert default dompurify`.
- The design above assumed the default policy could sanitize from the start.
  It cannot, safely: the browser calls the default policy even while the
  header is report-only, and what the policy returns is what reaches the DOM.
  So in this phase it **observes**: it returns every value unchanged and
  reports only when DOMPurify with `EDITOR_SANITIZE_CONFIG` would have changed
  it (`effective-directive: trusted-types-default-policy`,
  `violated-directive: html-would-change`). Script and cross-origin script-URL
  sinks are reported as they come.
- next-themes' script, which React re-renders on the client through
  `innerHTML` without executing it, is recognised by shape instead of being
  compared as HTML (`KNOWN_LIBRARY_SCRIPTS`).
- Measured in Chromium with the production headers: no Trusted Types
  violation remains (every library sink goes through the default policy), and
  an editor session with ordinary content produces no observation; a hostile
  paste produces one (`onerror` would be removed).
- What phase 4 needs from production: observations collected over a release
  cycle. Each one is either a gap in `EDITOR_SANITIZE_CONFIG` (content that
  must survive) or the policy doing its job (content that must not).

**Phase 3 — verify under enforcement. Done.**

- Bundle contract: `hangar-bundle-sinks` (`packages/csp/src/bundle-sinks.mjs`)
  scans the built web, admin and space bundles through hidden source maps
  (`HANGAR_BUNDLE_SOURCEMAPS=1`) and fails when a sink appears that
  `packages/csp/bundle-sinks/<app>.json` does not name, or when a named one
  disappears. Each entry carries a reviewed reason; `--update` rewrites the
  file for review. It runs in the web-apps pull-request workflow.
- Security suite: `apps/visual-tests/security/` runs on the visual suite's
  stack, after it (`pnpm vr`), because it writes. Every document gets the
  policy its build generated plus `require-trusted-types-for 'script'`,
  both **enforced**. Covered: the rich-text editor (stored table, palette
  colours, alignment, typing, a shortcut, markdown paste, two hostile pastes,
  saving through the API), a comment, a sticky, the workspace home and the
  instance console. A test fails on any violation, any Trusted Types error in
  the page, a missing default policy, and any default-policy observation
  except the hostile pastes' `onerror`/`onload`. A failed test attaches what
  the page reported, so a page that never renders says whether the policy
  stopped it.
- Mutation check: removing `default` from the enforced `trusted-types` list
  fails all five tests, with the refused policy in the diagnostics.
- Not covered: published boards (space) and pages (`live`), which the visual
  stack does not run, and the PDF export. They stay under the report-only
  measurement until the stack grows them.

**Phase 4 — enforce.** Move the two directives from the report-only header to
the enforced policy once the CSP itself is enforced and a release cycle has
produced no Trusted Types reports.

## Risks

- **Library upgrades change constants** (next-themes script, bprogress
  template). The exact-match tests fail at build time instead of in the
  browser, which is the point of having them.
- **DOMPurify changes pasted formatting.** The config is built from the editor's
  own tags and attributes and tested by round-tripping the editor's output;
  what it removes is what the editor schema would drop anyway.
- **A missed sink throws in production.** Mitigated by phases 0 and 3 and by
  enforcing only after a clean report-only cycle; the default policy reports
  unknown sinks instead of throwing, so the first sign is a report, not a broken
  page.
