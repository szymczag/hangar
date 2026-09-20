/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { getEditorAssetDownloadSrc, getEditorAssetSrc } from "./editor/common";
import { isAssetId } from "./asset-id";

const ASSET_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";

describe("isAssetId", () => {
  it("accepts an API-issued asset id", () => {
    expect(isAssetId(ASSET_ID)).toBe(true);
    expect(isAssetId(ASSET_ID.toUpperCase())).toBe(true);
  });

  it.each([
    "",
    "..",
    "../../workspaces/x",
    `${ASSET_ID}/../../x`,
    `${ASSET_ID}?x=1`,
    "https://cdn.example/a.png",
    null,
    42,
  ])("refuses %j", (value) => {
    expect(isAssetId(value)).toBe(false);
  });
});

describe("editor asset paths", () => {
  // An image src in user content becomes a path for display, delete, restore
  // and duplicate requests. A traversal must not become one.
  it("builds a path only from an asset id", () => {
    expect(getEditorAssetSrc({ assetId: ASSET_ID, workspaceSlug: "ws", projectId: "p" })).toContain(`/${ASSET_ID}/`);
    expect(
      getEditorAssetSrc({ assetId: "../../../../workspaces/ws/projects/p", workspaceSlug: "ws", projectId: "p" })
    ).toBeUndefined();
    expect(getEditorAssetDownloadSrc({ assetId: "../x", workspaceSlug: "ws" })).toBeUndefined();
  });
});
