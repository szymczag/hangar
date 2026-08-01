/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import {
  isAssetId,
  isSafeAssetUrl,
  isValidAssetReference,
  MAX_PDF_IMAGE_BYTES,
  readBoundedImageResponse,
} from "@/lib/asset-fetch-security";

const ASSET_ID = "92fafb42-c793-4990-9c52-23e77baa6079";
const PROJECT_ID = "02b026fa-1455-4ab1-9235-a94104ca2d34";

describe("PDF asset fetch security", () => {
  it("accepts only canonical asset references", () => {
    expect(isAssetId(ASSET_ID)).toBe(true);
    expect(isAssetId("../../metadata")).toBe(false);
    expect(isValidAssetReference("workspace-1", ASSET_ID, PROJECT_ID)).toBe(true);
    expect(isValidAssetReference("workspace/../admin", ASSET_ID, PROJECT_ID)).toBe(false);
    expect(isValidAssetReference("workspace-1", ASSET_ID, "not-a-uuid")).toBe(false);
  });

  it("rejects non-HTTP and credential-bearing asset URLs", () => {
    expect(isSafeAssetUrl("https://objects.example.com/image.png?signature=value")).toBe(true);
    expect(isSafeAssetUrl("http://minio.internal/image.png")).toBe(true);
    expect(isSafeAssetUrl("file:///etc/passwd")).toBe(false);
    expect(isSafeAssetUrl("https://user:secret@objects.example.com/image.png")).toBe(false);
    expect(isSafeAssetUrl("not a URL")).toBe(false);
  });

  it("bounds and content-types image responses", async () => {
    const valid = new Response(new Uint8Array([1, 2, 3]), {
      headers: { "content-type": "image/png", "content-length": "3" },
    });
    await expect(readBoundedImageResponse(valid)).resolves.toEqual(Buffer.from([1, 2, 3]));

    const wrongType = new Response(new Uint8Array([1]), {
      headers: { "content-type": "text/html" },
    });
    await expect(readBoundedImageResponse(wrongType)).rejects.toThrow("content type");

    const oversized = new Response(new Uint8Array([1]), {
      headers: {
        "content-type": "image/png",
        "content-length": String(MAX_PDF_IMAGE_BYTES + 1),
      },
    });
    await expect(readBoundedImageResponse(oversized)).rejects.toThrow("too large");
  });
});
