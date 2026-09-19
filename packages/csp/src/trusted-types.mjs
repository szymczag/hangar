/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Trusted Types policies for the frontends (docs/trusted-types-plan.md,
// phase 2). Browser-only: nothing here runs on import, and every function is
// a no-op where the Trusted Types API does not exist (Node, older browsers).
//
// Two policies:
//
// - "hangar-inert" is used only by parseInertHTML (@plane/utils), the one
//   place our code parses HTML, into a document with no browsing context.
//   It returns its input unchanged.
//
// - "default" is what the browser calls when library code hands a plain
//   string to a guarded sink (TipTap, tiptap-markdown, next-themes, the
//   progress bar …). The browser calls it even while the header is
//   report-only, and whatever it returns is what reaches the DOM. It therefore
//   OBSERVES in this phase: it returns every value unchanged, checks whether
//   DOMPurify with the editor's configuration would change it, and reports
//   only when it would. Those reports are the evidence phase 4 needs before
//   the policy is allowed to change anything.

import DOMPurify from "dompurify";

/** Policy names the Content-Security-Policy `trusted-types` directive allows. */
export const TRUSTED_TYPES_POLICY_NAMES = ["hangar-inert", "default", "dompurify"];

// Singletons live on globalThis so a second copy of this module (two bundles,
// a duplicated dependency) reuses the policies instead of failing to create
// them under the same names.
const INERT_POLICY = Symbol.for("hangar.trusted-types.inert-policy");
const INSTALLED = Symbol.for("hangar.trusted-types.installed");

// Values above this size are not compared: a whole page can be megabytes, and
// observing must never make the editor noticeably slower.
export const OBSERVE_MAX_LENGTH = 200_000;

/**
 * DOMPurify configuration that keeps the editor's own markup intact: its
 * custom elements, and the attributes its nodes and the server allowlist
 * (apps/api/plane/utils/content_validator.py) use. data-* attributes are
 * allowed by DOMPurify's defaults. Inline style is not.
 */
export const EDITOR_SANITIZE_CONFIG = Object.freeze({
  ADD_TAGS: ["image-component", "mention-component", "issue-embed-component"],
  ADD_ATTR: [
    "entity_identifier",
    "entity_name",
    "alignment",
    "status",
    "aspectratio",
    "colwidth",
    "background",
    "textcolor",
    "language",
    "target",
  ],
  FORBID_ATTR: ["style"],
});

/**
 * Library scripts that React renders again on the client through innerHTML.
 * React creates such script elements so that they never execute; the copy
 * that runs is the one served in the document, which the Content-Security-
 * Policy allowed by hash or nonce. Their text is JavaScript, so comparing it
 * with an HTML sanitizer only reports minified `<` comparisons as tags.
 * Matched by shape rather than exact text: the served copy and the client
 * copy are the same function minified differently.
 */
export const KNOWN_LIBRARY_SCRIPTS = Object.freeze([
  {
    // next-themes' anti-flash script: an IIFE over the root element that reads
    // the stored theme and the colour-scheme media query.
    name: "next-themes",
    matches: (value) =>
      /^\(\([\w$,]+\)=>\{let [\w$]+=document\.documentElement,[\w$]+=\[["'`]light["'`],["'`]dark["'`]\];/.test(value) &&
      value.includes("localStorage.getItem(") &&
      value.includes("prefers-color-scheme: dark"),
  },
]);

const isKnownLibraryScript = (value) => KNOWN_LIBRARY_SCRIPTS.some((script) => script.matches(value));

const trustedTypesApi = () => globalThis.trustedTypes;

/**
 * The HTML string as a TrustedHTML from "hangar-inert", for DOMParser only.
 * Returns the string itself where Trusted Types does not exist.
 */
export const inertHTML = (html) => {
  const api = trustedTypesApi();
  if (!api?.createPolicy) return html;
  let policy = globalThis[INERT_POLICY];
  if (!policy) {
    try {
      policy = api.createPolicy("hangar-inert", { createHTML: (value) => value });
    } catch {
      // Not creatable (a policy of that name exists, or the header does not
      // allow it). Where Trusted Types is not enforced the plain string still
      // parses; where it is, the parse fails closed, which is correct.
      return html;
    }
    globalThis[INERT_POLICY] = policy;
  }
  return policy.createHTML(html);
};

/** The value's markup as the HTML parser would serialize it. */
const canonicalHTML = (value) => new DOMParser().parseFromString(inertHTML(value), "text/html").body.innerHTML;

const firstDifference = (a, b) => {
  let index = 0;
  while (index < a.length && index < b.length && a[index] === b[index]) index += 1;
  return index;
};

const isSameOrigin = (value) => {
  try {
    return new URL(String(value), globalThis.location?.href).origin === globalThis.location?.origin;
  } catch {
    return false;
  }
};

/**
 * Creates the default policy. Call once, first thing in the client entry,
 * before React renders. `reportUrl` receives one report per distinct finding
 * per page load. `sanitize` and `send` exist for tests.
 */
export const installTrustedTypesPolicies = ({
  reportUrl = "/api/csp-report/",
  sanitize = (value) => DOMPurify.sanitize(value, EDITOR_SANITIZE_CONFIG),
  send = (url, body) => globalThis.navigator?.sendBeacon?.(url, new Blob([body], { type: "text/plain" })),
} = {}) => {
  const api = trustedTypesApi();
  if (!api?.createPolicy || globalThis[INSTALLED]) return false;
  globalThis[INSTALLED] = true;

  // Inline scripts the document was served with (the next-themes script, React
  // Router's context). The Content-Security-Policy already authorized each by
  // hash or nonce; when React renders the same text again through innerHTML,
  // it is that script, not markup, and comparing it with an HTML sanitizer
  // would report its minified `<` comparisons as tags.
  const servedInlineScripts = new Set(
    Array.from(globalThis.document?.scripts ?? [])
      .filter((script) => !script.src)
      .map((script) => script.textContent ?? "")
  );

  const reported = new Set();
  const report = (finding, sink, sample) => {
    const key = `${finding}|${sink}|${sample.slice(0, 60)}`;
    if (reported.has(key)) return;
    reported.add(key);
    try {
      send(
        reportUrl,
        JSON.stringify({
          "csp-report": {
            "document-uri": String(globalThis.location?.href ?? ""),
            "effective-directive": "trusted-types-default-policy",
            "violated-directive": finding,
            "blocked-uri": sink,
            disposition: "observe",
            "script-sample": sample.slice(0, 200),
          },
        })
      );
    } catch {
      // Observing must never break the page.
    }
  };

  let observing = false;
  const observeHTML = (value, sink) => {
    if (observing || value.length > OBSERVE_MAX_LENGTH || servedInlineScripts.has(value) || isKnownLibraryScript(value))
      return;
    observing = true;
    try {
      const canonical = canonicalHTML(value);
      const sanitized = String(sanitize(value));
      if (canonical !== sanitized) {
        const at = firstDifference(canonical, sanitized);
        report("html-would-change", sink, canonical.slice(Math.max(0, at - 40), at + 160));
      }
    } catch {
      // Observing must never break the page.
    } finally {
      observing = false;
    }
  };

  try {
    api.createPolicy("default", {
      createHTML: (value, _type, sink) => {
        // ProseMirror calls the default policy directly, without a sink name.
        observeHTML(String(value), sink ? String(sink) : "direct call");
        return value;
      },
      createScript: (value, _type, sink) => {
        report("script", String(sink), String(value));
        return value;
      },
      createScriptURL: (value, _type, sink) => {
        if (!isSameOrigin(value)) report("script-url", String(sink), String(value));
        return value;
      },
    });
  } catch {
    // Something already created a default policy. Starting the page matters
    // more than observing it; the report-only header still reports sinks.
    return false;
  }
  return true;
};
