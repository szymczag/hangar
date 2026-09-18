/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Browsers execute these protocols in the page's security context.
const BLOCKED_LINK_PROTOCOLS = ["javascript:", "data:", "vbscript:"];

/**
 * Returns true if the raw href value contains a dangerous protocol.
 *
 * WHATWG URL parsing removes ASCII Tab, LF, and CR anywhere in the input and
 * ignores leading C0 controls and whitespace before parsing the scheme.
 */
export function isDangerousHref(rawHref: string): boolean {
  const normalized = rawHref
    .replace(/[\t\n\r]/g, "")
    // oxlint-disable-next-line no-control-regex -- stripping C0 controls is the point: browsers ignore them before a scheme
    .replace(/^(?:[\u0000-\u001f]|\s)+/, "")
    .toLowerCase();

  return BLOCKED_LINK_PROTOCOLS.some((protocol) => normalized.startsWith(protocol));
}

// Schemes a click on an editor link may open. Anything else is ignored.
const NAVIGABLE_LINK_PROTOCOLS = new Set(["http:", "https:", "mailto:", "tel:"]);

/**
 * Returns true only for an href the editor may open on click: it must parse as
 * a URL and use an allowlisted scheme. An allowlist, unlike the blocklist
 * above, does not depend on knowing every executable scheme.
 */
export function isNavigableHref(rawHref: string): boolean {
  if (!rawHref || isDangerousHref(rawHref)) return false;
  try {
    return NAVIGABLE_LINK_PROTOCOLS.has(new URL(rawHref).protocol);
  } catch {
    return false;
  }
}
