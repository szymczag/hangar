/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { getAssetIdFromUrl } from "./file";

describe("getAssetIdFromUrl", () => {
  it.each([
    ["https://cdn.example/ws-id/abc-image.png", "abc-image.png"],
    ["https://cdn.example/ws-id/image.png?id=5614&token=xyz", "image.png"],
    ["https://cdn.example/ws-id/10315?size=medium", "10315"],
    ["https://cdn.example/ws-id/thumb.png#frag", "thumb.png"],
    ["https://cdn.example/ws-id/image.png/?id=5614", "image.png"],
    ["/api/assets/v2/workspaces/ws/3fa85f64-5717-4562-b3fc-2c963f66afa6/", "3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    ["asset-uuid", "asset-uuid"],
  ])("extracts the asset id from %j", (input, expected) => {
    expect(getAssetIdFromUrl(input)).toBe(expected);
  });
});
