/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { hasRenderableEmoji } from "../src/core/extensions/emoji/emoji-support";

describe("hasRenderableEmoji", () => {
  it("accepts an emoji item with a native Unicode representation", () => {
    expect(
      hasRenderableEmoji({
        emoji: "😀",
        name: "grinning",
        shortcodes: ["grinning"],
        tags: [],
      })
    ).toBe(true);
  });

  it.each([undefined, ""])("rejects an item without a native Unicode representation", (emoji) => {
    expect(
      hasRenderableEmoji({
        emoji,
        name: "custom",
        shortcodes: ["custom"],
        tags: [],
      })
    ).toBe(false);
  });
});
