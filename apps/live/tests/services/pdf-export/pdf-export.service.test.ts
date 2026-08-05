/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Effect } from "effect";
import { describe, expect, it, vi } from "vitest";
import { MAX_PDF_IMAGE_COUNT } from "@/lib/asset-fetch-security";
import { PdfExportService } from "@/services/pdf-export";

vi.hoisted(() => {
  process.env.API_BASE_URL = "http://api.test";
  process.env.LIVE_SERVER_SECRET_KEY = "unit-test-live-secret";
});

const getImageReferences = (document: {
  type: string;
  content?: Array<{ type: string; attrs?: Record<string, unknown> }>;
}) =>
  Effect.runSync(
    Effect.gen(function* () {
      const service = yield* PdfExportService;
      return service.extractImageReferences(document);
    }).pipe(Effect.provide(PdfExportService.Default))
  );

describe("PdfExportService image reference extraction", () => {
  it("prefetches valid application assets and generic remote/data images", () => {
    const assetId = "92fafb42-c793-4990-9c52-23e77baa6079";
    const dataUri = `data:image/png;base64,${Buffer.from([1, 2, 3]).toString("base64")}`;

    expect(
      getImageReferences({
        type: "doc",
        content: [
          { type: "imageComponent", attrs: { src: assetId } },
          { type: "image", attrs: { src: "https://images.example.com/picture.png" } },
          { type: "image", attrs: { src: dataUri } },
        ],
      })
    ).toEqual([assetId, "https://images.example.com/picture.png", dataUri]);
  });

  it("fails closed for URL-valued image components and filesystem paths", () => {
    expect(
      getImageReferences({
        type: "doc",
        content: [
          { type: "imageComponent", attrs: { src: "http://api:8000/private" } },
          { type: "image", attrs: { src: "../../etc/passwd" } },
          { type: "image", attrs: { src: "file:///etc/passwd" } },
        ],
      })
    ).toEqual([]);
  });

  it("caps the number of document-controlled image references", () => {
    const content = Array.from({ length: MAX_PDF_IMAGE_COUNT + 10 }, (_, index) => ({
      type: "image",
      attrs: { src: `https://images.example.com/${index}.png` },
    }));

    expect(getImageReferences({ type: "doc", content })).toHaveLength(MAX_PDF_IMAGE_COUNT);
  });
});
