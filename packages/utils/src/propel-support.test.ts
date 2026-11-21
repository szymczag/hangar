/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Hangar: helpers taken from upstream v1.5.0 because @plane/blocks imports them.

import { describe, expect, it } from "vitest";
import { cn } from "./common";
import { measureTextWidth } from "./measure-text";
import { getAvatarName } from "./string";

describe("getAvatarName", () => {
  it.each([
    ["sibira.gopal (you)", "sibira.gopal"],
    ["Jane Doe", "Jane Doe"],
    ["  Jane   Doe  ", "Jane Doe"],
    [null, ""],
    [undefined, ""],
  ])("maps %j to %j", (label, expected) => {
    expect(getAvatarName(label)).toBe(expected);
  });
});

describe("measureTextWidth", () => {
  it("returns 0 for empty text", () => {
    expect(measureTextWidth("")).toBe(0);
  });

  it("falls back to an average-glyph estimate without a canvas", () => {
    // Node has no OffscreenCanvas or document: 4 glyphs x 12px x 0.6, rounded up.
    expect(measureTextWidth("abcd")).toBe(29);
    expect(measureTextWidth("abcd", "500 20px Inter")).toBe(48);
  });
});

describe("cn with Propel width tokens", () => {
  it("keeps a named border width next to a border colour", () => {
    expect(cn("border-sm", "border-subtle-1")).toBe("border-sm border-subtle-1");
  });

  it("lets a later border width replace an earlier one", () => {
    expect(cn("border", "border-md")).toBe("border-md");
    expect(cn("outline-sm", "outline-lg")).toBe("outline-lg");
  });
});
