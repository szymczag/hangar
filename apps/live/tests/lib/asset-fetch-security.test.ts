/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { lookup } from "node:dns/promises";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  isAssetId,
  isSafePdfImageDataUri,
  isSafeAssetUrl,
  isValidAssetReference,
  MAX_PDF_IMAGE_BYTES,
  pinnedAssetFetch,
  readBoundedImageDataUri,
  readBoundedImageResponse,
  resolveAndValidateAssetHost,
} from "@/lib/asset-fetch-security";

vi.mock("node:dns/promises", async (importOriginal) => ({
  ...(await importOriginal<typeof import("node:dns/promises")>()),
  lookup: vi.fn(),
}));

const ASSET_ID = "92fafb42-c793-4990-9c52-23e77baa6079";
const PROJECT_ID = "02b026fa-1455-4ab1-9235-a94104ca2d34";

describe("PDF asset fetch security", () => {
  afterEach(() => vi.clearAllMocks());

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

  it("validates every DNS answer and rejects mixed public/private results", async () => {
    vi.mocked(lookup).mockResolvedValueOnce([
      { address: "93.184.216.34", family: 4 },
      { address: "127.0.0.1", family: 4 },
    ] as never);

    await expect(resolveAndValidateAssetHost("images.example.com")).rejects.toThrow("private");
  });

  it("rejects IPv4, IPv6, and transition addresses that can reach internal networks", async () => {
    for (const address of [
      "169.254.169.254",
      "::1",
      "::ffff:127.0.0.1",
      "64:ff9b::7f00:1",
      "2002:7f00:1::",
      "3fff::1",
      "5f00::1",
    ]) {
      vi.mocked(lookup).mockResolvedValueOnce([{ address, family: address.includes(":") ? 6 : 4 }] as never);
      // oxlint-disable-next-line no-await-in-loop -- each address is a separate resolver verdict
      await expect(resolveAndValidateAssetHost("attacker.example")).rejects.toThrow("private");
    }
  });

  it("permits an exact operator-trusted internal host but still pins the connection", async () => {
    let receivedHost = "";
    const server = createServer((request, response) => {
      receivedHost = request.headers.host ?? "";
      response.writeHead(200, { "content-type": "image/png" });
      response.end(Buffer.from([1, 2, 3]));
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const { port } = server.address() as AddressInfo;
    vi.mocked(lookup).mockResolvedValue([{ address: "127.0.0.1", family: 4 }] as never);

    try {
      const response = await pinnedAssetFetch(`http://storage.internal.test:${port}/asset`, {
        allowedHosts: new Set(["storage.internal.test"]),
      });
      await expect(readBoundedImageResponse(response)).resolves.toEqual(Buffer.from([1, 2, 3]));
      expect(receivedHost).toBe(`storage.internal.test:${port}`);
      expect(lookup).toHaveBeenCalledTimes(1);
    } finally {
      await new Promise<void>((resolve, reject) => {
        server.close((error) => {
          if (error) reject(error);
          else resolve();
        });
      });
    }
  });

  it("revalidates redirect destinations before opening the next socket", async () => {
    const server = createServer((_request, response) => {
      response.writeHead(302, { location: "http://metadata.attacker.test/latest" });
      response.end();
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const { port } = server.address() as AddressInfo;
    vi.mocked(lookup)
      .mockResolvedValueOnce([{ address: "127.0.0.1", family: 4 }] as never)
      .mockResolvedValueOnce([{ address: "169.254.169.254", family: 4 }] as never);

    try {
      await expect(
        pinnedAssetFetch(`http://storage.internal.test:${port}/redirect`, {
          allowedHosts: new Set(["storage.internal.test"]),
        })
      ).rejects.toThrow("private");
      expect(lookup).toHaveBeenCalledTimes(2);
    } finally {
      await new Promise<void>((resolve, reject) => {
        server.close((error) => {
          if (error) reject(error);
          else resolve();
        });
      });
    }
  });

  it("accepts only bounded base64 image data URIs", () => {
    const valid = `data:image/png;base64,${Buffer.from([1, 2, 3]).toString("base64")}`;
    expect(readBoundedImageDataUri(valid)).toEqual(Buffer.from([1, 2, 3]));
    expect(isSafePdfImageDataUri(valid)).toBe(true);
    expect(isSafePdfImageDataUri("data:text/html;base64,PHNjcmlwdD4=")).toBe(false);
    expect(isSafePdfImageDataUri("file:///etc/passwd")).toBe(false);
  });
});
