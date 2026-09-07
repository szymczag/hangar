/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { mergeAttributes } from "@tiptap/core";
import { describe, expect, it } from "vitest";

describe("mergeAttributes prototype safety", () => {
  it("keeps a JSON __proto__ key as data instead of inheriting DOM attributes", () => {
    const input = JSON.parse('{"__proto__":{"src":"x-invalid://canary","onerror":"globalThis.__tiptapXss += 1"}}');

    const attributes = mergeAttributes(input);

    expect(Object.getPrototypeOf(attributes)).toBe(Object.prototype);
    expect(Object.prototype.hasOwnProperty.call(attributes, "__proto__")).toBe(true);
    expect(attributes.src).toBeUndefined();
    expect(attributes.onerror).toBeUndefined();
  });
});
