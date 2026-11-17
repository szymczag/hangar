/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { validateOptionalPersonName, validatePersonName } from "./validation";

describe("validatePersonName", () => {
  it.each(["", "   "])("still requires a first name (%j)", (name) => {
    expect(validatePersonName(name)).toBe("Name is required");
  });

  it("accepts a plain name", () => {
    expect(validatePersonName("Jean-Paul")).toBe(true);
  });
});

describe("validateOptionalPersonName", () => {
  it.each(["", "   ", undefined])("accepts an empty last name (%j)", (name) => {
    expect(validateOptionalPersonName(name)).toBe(true);
  });

  it("accepts a plain name", () => {
    expect(validateOptionalPersonName("Smith")).toBe(true);
  });

  it("applies the person name rules to a non-empty value", () => {
    expect(validateOptionalPersonName("Smith<script>")).toBe(validatePersonName("Smith<script>"));
    expect(validateOptionalPersonName("Smith<script>")).not.toBe(true);
    expect(validateOptionalPersonName("x".repeat(51))).toBe("Name must be 50 characters or less");
    expect(validateOptionalPersonName("R2D2")).toBe("Names can only contain letters, spaces, hyphens, and apostrophes");
  });
});
