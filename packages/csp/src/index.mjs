/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// The Content-Security-Policy each frontend sends. It lives with the frontends
// because it describes them: where their scripts come from, what they inline,
// which origins they talk to. A change to one of those and the matching change
// to the policy belong in the same commit.
//
// No source list here contains 'unsafe-inline', 'unsafe-eval' or
// 'wasm-unsafe-eval'. Inline scripts are allowed by hash (static single-page
// builds) or by a per-request nonce (server-rendered space). Inline style
// attributes are refused outright; the editor renders colour and alignment as
// data attributes styled by its stylesheet.

import { createHash } from "node:crypto";

/**
 * `<style>` elements that libraries insert at runtime with fixed content.
 * Allowed by hash; tests/runtime-styles.test.mjs checks each one against the
 * installed library so an upgrade that changes it fails the build, not users.
 *
 * - Base UI ScrollArea/Select: hides the native scrollbar.
 */
export const RUNTIME_STYLE_ELEMENTS = [
  ".base-ui-disable-scrollbar{scrollbar-width:none}.base-ui-disable-scrollbar::-webkit-scrollbar{display:none}",
];

/**
 * Origins the frontends reach whatever the deployment:
 *
 * - connect-src cdn.jsdelivr.net: the emoji picker (frimousse) loads its
 *   emoji data (JSON, not scripts) from there.
 *
 * Images are only ever this instance's own: its bundle, uploads in object
 * storage, and blob:/data: URLs made in the page. No image is loaded from
 * another host -- not a profile picture from an identity provider (those are
 * copied to object storage), not a cover from Unsplash, not an image a
 * description points at.
 *
 * Origins that depend on the deployment (object storage, a separate API or
 * live origin, a self-hosted GitLab's avatars) come from the environment.
 */
export const APP_SOURCES = {
  connectSrc: ["https://cdn.jsdelivr.net"],
  imgSrc: [],
};

/** `'sha256-…'` source expression for an exact inline script or style body. */
export const hashSource = (content) => `'sha256-${createHash("sha256").update(content, "utf8").digest("base64")}'`;

const INLINE_SCRIPT = /<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi;

/**
 * Hash sources for every inline `<script>` in an HTML document. Scripts with a
 * `src` are external and covered by 'self'.
 */
export const inlineScriptHashes = (html) => {
  const hashes = [];
  for (const [, attributes, body] of html.matchAll(INLINE_SCRIPT)) {
    if (/\bsrc\s*=/i.test(attributes)) continue;
    hashes.push(hashSource(body));
  }
  return [...new Set(hashes)];
};

const sourceList = (...parts) =>
  parts
    .flatMap((part) => (Array.isArray(part) ? part : String(part ?? "").split(/\s+/)))
    .map((source) => source.trim())
    .filter(Boolean)
    .join(" ");

/**
 * Builds the policy string.
 *
 * `scriptSources` and `styleElementSources` are the hash or nonce sources for
 * inline code. The remaining options are operator-supplied origins (object
 * storage, a separate API or live origin, avatar hosts) appended to 'self'.
 */
export const buildContentSecurityPolicy = ({
  scriptSources = [],
  styleElementSources = [],
  imgSrc = "",
  connectSrc = "",
  mediaSrc = "",
  frameSrc = "",
  formAction = "",
  frameAncestors = "'none'",
  reportUri = "",
} = {}) => {
  const directives = [
    ["default-src", "'self'"],
    ["script-src", sourceList("'self'", scriptSources)],
    ["script-src-attr", "'none'"],
    ["style-src", "'self'"],
    ["style-src-elem", sourceList("'self'", styleElementSources)],
    ["style-src-attr", "'none'"],
    ["img-src", sourceList("'self'", "blob:", "data:", APP_SOURCES.imgSrc, imgSrc)],
    ["font-src", "'self'"],
    ["media-src", sourceList("'self'", mediaSrc)],
    ["connect-src", sourceList("'self'", APP_SOURCES.connectSrc, connectSrc)],
    ["worker-src", "'self'"],
    ["manifest-src", "'self'"],
    ["frame-src", sourceList(frameSrc) || "'none'"],
    ["form-action", sourceList("'self'", formAction)],
    ["frame-ancestors", sourceList(frameAncestors) || "'none'"],
    ["object-src", "'none'"],
    ["base-uri", "'self'"],
  ];
  if (reportUri) directives.push(["report-uri", reportUri]);
  return directives.map(([name, value]) => `${name} ${value}`).join("; ");
};

// Enforced by default. Every screen of the visual suite and the security
// suite's flows run under this policy enforced (docs/content-security-policy.md,
// "Verification"). HANGAR_CSP_REPORT_ONLY=true sends it report-only instead,
// for a deployment that wants to watch its reports first. The nginx images take
// the same defaults from nginx/15-hangar-csp.envsh.
export const DEFAULT_REPORT_ONLY = false;
export const DEFAULT_REPORT_URI = "/api/csp-report/";

/**
 * Runtime origins, read from the environment the frontend runs in. Every
 * origin variable is optional; unset means only 'self' and APP_SOURCES.
 */
export const runtimeSourcesFromEnv = (env = process.env) => ({
  imgSrc: env.HANGAR_CSP_IMG_SRC ?? "",
  connectSrc: env.HANGAR_CSP_CONNECT_SRC ?? "",
  mediaSrc: env.HANGAR_CSP_MEDIA_SRC ?? "",
  frameSrc: env.HANGAR_CSP_FRAME_SRC ?? "",
  formAction: env.HANGAR_CSP_FORM_ACTION ?? "",
  reportUri: env.HANGAR_CSP_REPORT_URI ?? DEFAULT_REPORT_URI,
});

/** Response header name: enforcing, or report-only while a rollout is observed. */
export const policyHeaderName = (env = process.env) => {
  const reportOnly = env.HANGAR_CSP_REPORT_ONLY ? env.HANGAR_CSP_REPORT_ONLY === "true" : DEFAULT_REPORT_ONLY;
  return reportOnly ? "Content-Security-Policy-Report-Only" : "Content-Security-Policy";
};

// Trusted Types (docs/trusted-types-plan.md).
//
// Sent as its own header, separate from the policy above, so its mode does not
// follow HANGAR_CSP_REPORT_ONLY: enforcing the main policy does not start
// enforcing Trusted Types, and HANGAR_CSP_TRUSTED_TYPES=enforce enforces them
// even while the main policy only reports. The browser reports policy creation
// as well as every sink that receives a plain string. `trusted-types` names
// the policies @plane/csp/trusted-types creates (and DOMPurify's own), so any
// other policy a library creates is reported, or refused when enforced.
export const TRUSTED_TYPES_MEASUREMENT =
  "require-trusted-types-for 'script'; trusted-types hangar-inert default dompurify";

export { trustedTypesModeFromEnv } from "./trusted-types-mode.mjs";

/** The header that carries the Trusted Types policy in the given mode. */
export const trustedTypesHeaderName = (mode = "report") =>
  mode === "enforce" ? "Content-Security-Policy" : "Content-Security-Policy-Report-Only";

/** The Trusted Types policy, or "" when it is off. */
export const trustedTypesReportPolicy = ({ reportUri = "", mode = "report" } = {}) =>
  mode === "off"
    ? ""
    : [TRUSTED_TYPES_MEASUREMENT, reportUri ? `report-uri ${reportUri}` : ""].filter(Boolean).join("; ");
