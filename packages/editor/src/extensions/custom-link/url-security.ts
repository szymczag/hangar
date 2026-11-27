/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Browsers execute these protocols in the page's security context.
const BLOCKED_LINK_PROTOCOLS = ["javascript:", "data:", "vbscript:"];

/**
 * The raw href as the URL parser reads its scheme: WHATWG URL parsing removes
 * ASCII Tab, LF, and CR anywhere in the input and ignores leading C0 controls
 * and whitespace before parsing the scheme.
 */
const normalizeHrefForScheme = (rawHref: string): string =>
  rawHref
    .replace(/[\t\n\r]/g, "")
    // oxlint-disable-next-line no-control-regex -- stripping C0 controls is the point: browsers ignore them before a scheme
    .replace(/^(?:[\u0000-\u001f]|\s)+/, "")
    .toLowerCase();

/** Returns true if the raw href value contains a dangerous protocol. */
export function isDangerousHref(rawHref: string): boolean {
  const normalized = normalizeHrefForScheme(rawHref);
  return BLOCKED_LINK_PROTOCOLS.some((protocol) => normalized.startsWith(protocol));
}

/**
 * The schemes an editor link may carry: what the link inputs accept, what the
 * link mark keeps from pasted or stored HTML, and what a click may open. One
 * allowlist for all three, so a link the editor saved is one it would open.
 */
export const ALLOWED_LINK_PROTOCOLS: ReadonlySet<string> = new Set(["http:", "https:", "mailto:", "tel:"]);

/** True when `protocol` (as `URL#protocol` spells it, with the colon) is on the allowlist. */
export const isAllowedLinkProtocol = (protocol: string): boolean => ALLOWED_LINK_PROTOCOLS.has(protocol.toLowerCase());

// A scheme as the URL parser reads it: a letter, then letters, digits, "+", "-" or ".", then ":".
const EXPLICIT_SCHEME = /^([a-z][a-z0-9+.-]*):/;

/**
 * Returns true when a raw href may stay on a link mark. A relative reference
 * (`/path`, `#anchor`, `page?x=1`) has no scheme and stays; an href that names
 * a scheme must name an allowlisted one. Stricter than `isDangerousHref`, which
 * only knows the schemes that execute script: `intent:`, `blob:`,
 * `view-source:`, `ms-settings:` and the rest are refused because they are not
 * on the allowlist, not because each one is listed.
 */
export function isAllowedLinkHref(rawHref: string): boolean {
  if (isDangerousHref(rawHref)) return false;
  const scheme = EXPLICIT_SCHEME.exec(normalizeHrefForScheme(rawHref));
  return !scheme || isAllowedLinkProtocol(`${scheme[1]}:`);
}

/**
 * Returns true only for an href the editor may open on click: it must parse as
 * a URL and use an allowlisted scheme. An allowlist, unlike the blocklist
 * above, does not depend on knowing every executable scheme.
 */
export function isNavigableHref(rawHref: string): boolean {
  if (!rawHref || isDangerousHref(rawHref)) return false;
  try {
    return isAllowedLinkProtocol(new URL(rawHref).protocol);
  } catch {
    return false;
  }
}
