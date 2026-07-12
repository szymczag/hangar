/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { isDangerousHref } from "../src/core/extensions/custom-link/url-security";

describe("isDangerousHref", () => {
  it.each([
    "javascript:alert(1)",
    "JAVASCRIPT:alert(1)",
    "\tjavascript:alert(1)",
    "\u0000javascript:alert(1)",
    " \u0000 javascript:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
  ])("blocks dangerous href %j", (href) => {
    expect(isDangerousHref(href)).toBe(true);
  });

  it.each(["https://example.com", "http://example.com", "mailto:user@example.com", "/relative/path", "#anchor"])(
    "allows safe href %j",
    (href) => {
      expect(isDangerousHref(href)).toBe(false);
    }
  );
});
