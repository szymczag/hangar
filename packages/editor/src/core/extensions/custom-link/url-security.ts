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
    .replace(/^(?:[\u0000-\u001f]|\s)+/, "")
    .toLowerCase();

  return BLOCKED_LINK_PROTOCOLS.some((protocol) => normalized.startsWith(protocol));
}
