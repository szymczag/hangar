/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { isValidNextPath } from "./url";

describe("isValidNextPath", () => {
  it.each(["/", "/workspace/abc", "/projects/123/issues?tab=all", "  /dashboard  "])("accepts %j", (path) => {
    expect(isValidNextPath(path)).toBe(true);
  });

  it.each([
    "https://evil.com/phish",
    "http://evil.com/phish",
    "ftp://evil.com/",
    "http:evil.com",
    "javascript:alert(1)",
    "//evil.com/",
    "///evil.com/",
    "////evil.com/",
    "/\t/evil.com",
    "/\r/evil.com",
    "/\n/evil.com",
    "/\\evil.com",
    "dashboard",
    "",
  ])("rejects %j", (path) => {
    expect(isValidNextPath(path)).toBe(false);
  });
});
