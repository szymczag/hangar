/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export const MAX_PDF_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_PDF_IMAGE_COUNT = 50;

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const WORKSPACE_SLUG_PATTERN = /^[a-zA-Z0-9_-]{1,255}$/;
const PDF_IMAGE_CONTENT_TYPES = new Set(["image/gif", "image/jpeg", "image/png", "image/webp"]);

export const isAssetId = (value: string): boolean => UUID_PATTERN.test(value);

export const isValidAssetReference = (workspaceSlug: string, assetId: string, projectId?: string | null): boolean =>
  WORKSPACE_SLUG_PATTERN.test(workspaceSlug) && isAssetId(assetId) && (!projectId || UUID_PATTERN.test(projectId));

export const isSafeAssetUrl = (value: string): boolean => {
  try {
    const parsed = new URL(value);
    return (
      (parsed.protocol === "https:" || parsed.protocol === "http:") &&
      parsed.hostname.length > 0 &&
      parsed.username.length === 0 &&
      parsed.password.length === 0
    );
  } catch {
    return false;
  }
};

export const readBoundedImageResponse = async (response: Response): Promise<Buffer> => {
  const contentType = response.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase();
  if (!contentType || !PDF_IMAGE_CONTENT_TYPES.has(contentType)) {
    throw new Error("Unsupported PDF image content type");
  }

  const declaredLength = response.headers.get("content-length");
  if (declaredLength !== null) {
    const parsedLength = Number(declaredLength);
    if (!Number.isSafeInteger(parsedLength) || parsedLength < 0 || parsedLength > MAX_PDF_IMAGE_BYTES) {
      throw new Error("PDF image response is too large");
    }
  }

  if (!response.body) {
    throw new Error("PDF image response has no body");
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      // A response stream must be consumed serially to enforce the running byte cap.
      // oxlint-disable-next-line no-await-in-loop
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_PDF_IMAGE_BYTES) {
        // oxlint-disable-next-line no-await-in-loop
        await reader.cancel("PDF image response is too large");
        throw new Error("PDF image response is too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  return Buffer.concat(
    chunks.map((chunk) => Buffer.from(chunk)),
    size
  );
};
