/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { isWorkspaceSlug } from "@/lib/page-reference";

describe("isWorkspaceSlug", () => {
  it.each(["my-ws", "old.slug", "zespół", "ws\u{1F60A}"])("accepts %j, which encodes into a path", (slug) => {
    expect(isWorkspaceSlug(slug)).toBe(true);
    expect(() => encodeURIComponent(slug)).not.toThrow();
  });

  // encodeURIComponent throws URIError on a lone surrogate; the rule must refuse
  // it first, so a request with one is a 400 and not a failed export.
  it.each(["\ud800", "ws\ud83d", "\udc00", "a\udfffb", "\ude0a\ud83d"])("refuses the lone surrogate in %j", (slug) => {
    expect(() => encodeURIComponent(slug)).toThrow(URIError);
    expect(isWorkspaceSlug(slug)).toBe(false);
  });
});
