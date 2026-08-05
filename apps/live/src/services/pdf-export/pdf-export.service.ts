/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Effect } from "effect";
import sharp from "sharp";
import { getAllDocumentFormatsFromDocumentEditorBinaryData } from "@plane/editor/lib";
import type { PDFExportMetadata, TipTapDocument } from "@/lib/pdf";
import { renderPlaneDocToPdfBuffer } from "@/lib/pdf";
import {
  isAssetId,
  isSafeAssetUrl,
  MAX_PDF_IMAGE_COUNT,
  pinnedAssetFetch,
  readBoundedImageDataUri,
  readBoundedImageResponse,
} from "@/lib/asset-fetch-security";
import { env } from "@/env";
import { getPageService } from "@/services/page/handler";
import type { TDocumentTypes } from "@/types";
import {
  PdfContentFetchError,
  PdfGenerationError,
  PdfImageProcessingError,
  PdfTimeoutError,
} from "@/schema/pdf-export";
import { withTimeoutAndRetry, recoverWithDefault, tryAsync } from "./effect-utils";
import type { PdfExportInput, PdfExportResult, PageContent, MetadataResult } from "./types";

const IMAGE_CONCURRENCY = 4;
const IMAGE_TIMEOUT_MS = 8000;
const CONTENT_FETCH_TIMEOUT_MS = 7000;
const PDF_RENDER_TIMEOUT_MS = 15000;
const IMAGE_MAX_DIMENSION = 1200;
const PDF_ASSET_ALLOWED_HOSTS = new Set(
  env.PDF_ASSET_ALLOWED_HOSTS.split(",")
    .map((host) => host.trim().replace(/\.$/, "").toLowerCase())
    .filter(Boolean)
);

type TipTapNode = {
  type: string;
  attrs?: Record<string, unknown>;
  content?: TipTapNode[];
};

/**
 * PDF Export Service
 */
export class PdfExportService extends Effect.Service<PdfExportService>()("PdfExportService", {
  sync: () => ({
    /**
     * Determines document type
     */
    getDocumentType: (_input: PdfExportInput): TDocumentTypes => {
      return "project_page";
    },

    /**
     * Extracts every image reference from document content. The renderer never
     * receives these raw values; they must be resolved and re-encoded first.
     */
    extractImageReferences: (doc: TipTapNode): string[] => {
      const imageReferences: string[] = [];

      const traverse = (node: TipTapNode) => {
        if ((node.type === "imageComponent" || node.type === "image") && node.attrs?.src) {
          const src = node.attrs.src as string;
          const isValidReference =
            isAssetId(src) || (node.type === "image" && (isSafeAssetUrl(src) || src.startsWith("data:image/")));
          if (isValidReference && imageReferences.length < MAX_PDF_IMAGE_COUNT) {
            imageReferences.push(src);
          }
        }
        if (node.content) {
          for (const child of node.content) {
            traverse(child);
          }
        }
      };

      traverse(doc);
      return [...new Set(imageReferences)];
    },

    /**
     * Fetches page content (description binary) and parses it
     */
    fetchPageContent: (
      pageService: ReturnType<typeof getPageService>,
      pageId: string,
      requestId: string
    ): Effect.Effect<PageContent, PdfContentFetchError | PdfTimeoutError> =>
      Effect.gen(function* () {
        yield* Effect.logDebug("PDF_EXPORT: Fetching page content", { requestId, pageId });

        const descriptionBinary = yield* tryAsync(
          () => pageService.fetchDescriptionBinary(pageId),
          (cause) =>
            new PdfContentFetchError({
              message: "Failed to fetch page content",
              cause,
            })
        ).pipe(
          withTimeoutAndRetry("fetch page content", {
            timeoutMs: CONTENT_FETCH_TIMEOUT_MS,
            maxRetries: 3,
          })
        );

        if (!descriptionBinary) {
          return yield* Effect.fail(
            new PdfContentFetchError({
              message: "Page content not found",
            })
          );
        }

        const binaryData = new Uint8Array(descriptionBinary);
        const { contentJSON, titleHTML } = getAllDocumentFormatsFromDocumentEditorBinaryData(binaryData, true);

        return {
          contentJSON: contentJSON as TipTapDocument,
          titleHTML: titleHTML || null,
          descriptionBinary,
        };
      }),

    /**
     * Fetches user mentions for the page
     */
    fetchUserMentions: (
      pageService: ReturnType<typeof getPageService>,
      pageId: string,
      requestId: string
    ): Effect.Effect<MetadataResult> =>
      Effect.gen(function* () {
        yield* Effect.logDebug("PDF_EXPORT: Fetching user mentions", { requestId });

        const userMentionsRaw = yield* tryAsync(
          async () => {
            if (pageService.fetchUserMentions) {
              return await pageService.fetchUserMentions(pageId);
            }
            return [];
          },
          () => []
        ).pipe(recoverWithDefault([] as Array<{ id: string; display_name: string; avatar_url?: string }>));

        return {
          userMentions: userMentionsRaw.map((u) => ({
            id: u.id,
            display_name: u.display_name,
            avatar_url: u.avatar_url,
          })),
        };
      }),

    /**
     * Resolves and processes images for PDF embedding
     */
    processImages: (
      pageService: ReturnType<typeof getPageService>,
      workspaceSlug: string,
      projectId: string | undefined,
      imageReferences: string[],
      requestId: string
    ): Effect.Effect<Record<string, string>> =>
      Effect.gen(function* () {
        if (imageReferences.length === 0) {
          return {};
        }

        yield* Effect.logDebug("PDF_EXPORT: Processing images", {
          requestId,
          count: imageReferences.length,
        });

        // Resolve application asset IDs through Django. Generic image URLs and
        // data URIs remain keyed by their original src so the renderer can only
        // use a successfully processed replacement.
        const resolvedSourceMap = yield* tryAsync(
          async () => {
            const sourceMap = new Map<string, { data?: Buffer; url?: string }>();
            const resolvedSources = await Promise.all(
              imageReferences.map(async (reference) => {
                if (isAssetId(reference)) {
                  const url = await pageService.resolveImageAssetUrl?.(workspaceSlug, reference, projectId);
                  return { reference, url: url ?? undefined };
                }
                if (isSafeAssetUrl(reference)) return { reference, url: reference };
                try {
                  return { reference, data: readBoundedImageDataUri(reference) };
                } catch {
                  return { reference };
                }
              })
            );
            for (const { reference, data, url } of resolvedSources) {
              if (data || url) sourceMap.set(reference, { data, url });
            }
            return sourceMap;
          },
          () => new Map<string, { data?: Buffer; url?: string }>()
        ).pipe(recoverWithDefault(new Map<string, { data?: Buffer; url?: string }>()));

        if (resolvedSourceMap.size === 0) {
          return {};
        }

        // Process each image
        const processSingleImage = ([reference, source]: [string, { data?: Buffer; url?: string }]) =>
          Effect.gen(function* () {
            let imageBuffer = source.data;
            if (source.url) {
              const response = yield* tryAsync(
                () =>
                  pinnedAssetFetch(source.url as string, {
                    allowedHosts: PDF_ASSET_ALLOWED_HOSTS,
                    signal: AbortSignal.timeout(IMAGE_TIMEOUT_MS),
                  }),
                (cause) =>
                  new PdfImageProcessingError({
                    message: "Failed to fetch image",
                    assetId: isAssetId(reference) ? reference : "remote-image",
                    cause,
                  })
              );

              if (!response.ok) {
                yield* Effect.promise(() => response.body?.cancel() ?? Promise.resolve());
                return yield* Effect.fail(
                  new PdfImageProcessingError({
                    message: `Image fetch returned ${response.status}`,
                    assetId: isAssetId(reference) ? reference : "remote-image",
                  })
                );
              }

              imageBuffer = yield* tryAsync(
                () => readBoundedImageResponse(response),
                (cause) =>
                  new PdfImageProcessingError({
                    message: "Failed to read image body",
                    assetId: isAssetId(reference) ? reference : "remote-image",
                    cause,
                  })
              );
            }

            if (!imageBuffer) {
              return yield* Effect.fail(
                new PdfImageProcessingError({
                  message: "Image source was not resolved",
                  assetId: isAssetId(reference) ? reference : "remote-image",
                })
              );
            }

            const processedBuffer = yield* tryAsync(
              () =>
                sharp(imageBuffer)
                  .rotate()
                  .flatten({ background: { r: 255, g: 255, b: 255 } })
                  .resize(IMAGE_MAX_DIMENSION, IMAGE_MAX_DIMENSION, { fit: "inside", withoutEnlargement: true })
                  .jpeg({ quality: 85 })
                  .toBuffer(),
              (cause) =>
                new PdfImageProcessingError({
                  message: "Failed to process image",
                  assetId: isAssetId(reference) ? reference : "remote-image",
                  cause,
                })
            );

            const base64 = processedBuffer.toString("base64");
            return [reference, `data:image/jpeg;base64,${base64}`] as const;
          }).pipe(
            withTimeoutAndRetry(`process image ${isAssetId(reference) ? reference : "remote"}`, {
              timeoutMs: IMAGE_TIMEOUT_MS,
              maxRetries: 1,
            }),
            Effect.tapError((error) =>
              Effect.logWarning("PDF_EXPORT: Image processing failed", {
                requestId,
                assetId: isAssetId(reference) ? reference : "remote-image",
                error,
              })
            ),
            Effect.catchAll(() => Effect.succeed(null as readonly [string, string] | null))
          );

        const entries = Array.from(resolvedSourceMap.entries());
        const pairs = yield* Effect.forEach(entries, processSingleImage, {
          concurrency: IMAGE_CONCURRENCY,
        });

        const filtered = pairs.filter((p): p is readonly [string, string] => p !== null);
        return Object.fromEntries(filtered);
      }),

    /**
     * Renders document to PDF buffer
     */
    renderPdf: (
      contentJSON: TipTapDocument,
      metadata: PDFExportMetadata,
      options: {
        title?: string;
        author?: string;
        subject?: string;
        pageSize?: "A4" | "A3" | "A2" | "LETTER" | "LEGAL" | "TABLOID";
        pageOrientation?: "portrait" | "landscape";
        noAssets?: boolean;
      },
      requestId: string
    ): Effect.Effect<Buffer, PdfGenerationError | PdfTimeoutError> =>
      Effect.gen(function* () {
        yield* Effect.logDebug("PDF_EXPORT: Rendering PDF", { requestId });

        const pdfBuffer = yield* tryAsync(
          () =>
            renderPlaneDocToPdfBuffer(contentJSON, {
              title: options.title,
              author: options.author,
              subject: options.subject,
              pageSize: options.pageSize,
              pageOrientation: options.pageOrientation,
              metadata,
              noAssets: options.noAssets,
            }),
          (cause) =>
            new PdfGenerationError({
              message: "Failed to render PDF",
              cause,
            })
        ).pipe(withTimeoutAndRetry("render PDF", { timeoutMs: PDF_RENDER_TIMEOUT_MS, maxRetries: 0 }));

        yield* Effect.logInfo("PDF_EXPORT: PDF rendered successfully", {
          requestId,
          size: pdfBuffer.length,
        });

        return pdfBuffer;
      }),
  }),
}) {}

/**
 * Main export pipeline - orchestrates the entire PDF export process
 * Separate function to avoid circular dependency in service definition
 */
export const exportToPdf = (
  input: PdfExportInput
): Effect.Effect<PdfExportResult, PdfContentFetchError | PdfGenerationError | PdfTimeoutError, PdfExportService> =>
  Effect.gen(function* () {
    const service = yield* PdfExportService;
    const { requestId, pageId, workspaceSlug, projectId, noAssets } = input;

    yield* Effect.logInfo("PDF_EXPORT: Starting export", { requestId, pageId, workspaceSlug });

    // Create page service
    const documentType = service.getDocumentType(input);
    const pageService = getPageService(documentType, {
      workspaceSlug,
      projectId: projectId || null,
      cookie: input.cookie,
      documentType,
      userId: "",
    });

    // Fetch content
    const content = yield* service.fetchPageContent(pageService, pageId, requestId);

    // Extract image asset IDs
    const imageReferences = service.extractImageReferences(content.contentJSON as TipTapNode);

    // Fetch user mentions
    let metadata = yield* service.fetchUserMentions(pageService, pageId, requestId);

    // Process images if needed
    if (!noAssets && imageReferences.length > 0) {
      const resolvedImages = yield* service.processImages(
        pageService,
        workspaceSlug,
        projectId,
        imageReferences,
        requestId
      );
      metadata = { ...metadata, resolvedImageUrls: resolvedImages };
    }

    yield* Effect.logDebug("PDF_EXPORT: Metadata prepared", {
      requestId,
      userMentions: metadata.userMentions?.length ?? 0,
      resolvedImages: Object.keys(metadata.resolvedImageUrls ?? {}).length,
    });

    // Render PDF
    const documentTitle = input.title || content.titleHTML || undefined;
    const pdfBuffer = yield* service.renderPdf(
      content.contentJSON,
      metadata,
      {
        title: documentTitle,
        author: input.author,
        subject: input.subject,
        pageSize: input.pageSize,
        pageOrientation: input.pageOrientation,
        noAssets,
      },
      requestId
    );

    yield* Effect.logInfo("PDF_EXPORT: Export complete", {
      requestId,
      pageId,
      size: pdfBuffer.length,
    });

    return {
      pdfBuffer,
      outputFileName: input.fileName || `page-${pageId}.pdf`,
      pageId,
    };
  });
