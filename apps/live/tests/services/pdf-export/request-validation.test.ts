/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Either, Schema } from "effect";
import { describe, expect, it, vi } from "vitest";
import { logger } from "@plane/logger";

vi.mock("@plane/logger", () => ({
  logger: { log: vi.fn(), info: vi.fn(), error: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

// the export itself must never run for a refused body
const exportToPdf = vi.hoisted(() => vi.fn());
vi.mock("@/services/pdf-export", async () => {
  const { Effect, Layer } = await import("effect");
  return {
    exportToPdf: (...args: unknown[]) => {
      exportToPdf(...args);
      return Effect.die("export must not run");
    },
    PdfExportService: { Default: Layer.empty },
  };
});

import { PdfExportController } from "@/controllers/pdf-export.controller";
import { PdfExportRequestBody } from "@/schema/pdf-export";

const PAGE_ID = "11111111-1111-4111-8111-111111111111";
const PROJECT_ID = "22222222-2222-4222-8222-222222222222";
const valid = { pageId: PAGE_ID, workspaceSlug: "my-ws", projectId: PROJECT_ID };

const decode = (body: unknown) => Schema.decodeUnknownEither(PdfExportRequestBody)(body);

// A lone UTF-16 surrogate, as JSON "\ud800" decodes, makes encodeURIComponent throw.
const LONE_SURROGATE_SLUGS = ["\ud800", "ws\udfff", "a\udc00b", "\udc00\ud800"];
const BAD_SLUGS = ["../other", "..", ".", "a/b", "a\\b", "a?b", "a#b", "a%2Fb", "a\nb", "", ...LONE_SURROGATE_SLUGS];
const BAD_IDS = ["not-a-uuid", `${PAGE_ID}/x`, `../${PAGE_ID}`, `${PAGE_ID}?a=b`, ""];

describe("PdfExportRequestBody", () => {
  it.each(["my-ws", "ws_1", "Acme", "old.slug", "zespół", "ws\u{1F60A}"])(
    "accepts workspace slug %j",
    (workspaceSlug) => {
      expect(Either.isRight(decode({ ...valid, workspaceSlug }))).toBe(true);
    }
  );

  it("accepts a body without a project id", () => {
    expect(Either.isRight(decode({ pageId: PAGE_ID, workspaceSlug: "ws" }))).toBe(true);
  });

  it.each(BAD_SLUGS)("refuses workspace slug %j", (workspaceSlug) => {
    expect(Either.isLeft(decode({ ...valid, workspaceSlug }))).toBe(true);
  });

  it.each(BAD_IDS)("refuses page id %j", (pageId) => {
    expect(Either.isLeft(decode({ ...valid, pageId }))).toBe(true);
  });

  it.each(BAD_IDS)("refuses project id %j", (projectId) => {
    expect(Either.isLeft(decode({ ...valid, projectId }))).toBe(true);
  });
});

describe("PdfExportController", () => {
  const post = async (body: unknown) => {
    const res = { status: vi.fn(), json: vi.fn(), setHeader: vi.fn(), send: vi.fn() };
    res.status.mockReturnValue(res);
    await new PdfExportController().exportToPdf({ headers: { cookie: "session=c" }, body } as never, res as never);
    return res;
  };

  it.each([
    ["a traversing slug", { ...valid, workspaceSlug: "../../other" }],
    ["a slug with a query", { ...valid, workspaceSlug: "ws?x=1" }],
    ["a slug with a fragment", { ...valid, workspaceSlug: "ws#x" }],
    ["a slug with a slash", { ...valid, workspaceSlug: "ws/projects" }],
    ["a slug with a lone surrogate", JSON.parse(`{"pageId":"${PAGE_ID}","workspaceSlug":"ws\\ud800"}`) as unknown],
    ["a non-UUID page id", { ...valid, pageId: "../members" }],
    ["a non-UUID project id", { ...valid, projectId: "p/../../x" }],
  ])("answers 400 for %s without exporting", async (_label, body) => {
    exportToPdf.mockClear();
    const res = await post(body);
    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith({ message: "Invalid request body" });
    expect(exportToPdf).not.toHaveBeenCalled();
  });

  it("logs the refusal through the shared logger, not Effect's console logger", async () => {
    vi.mocked(logger.log).mockClear();
    await post({ ...valid, workspaceSlug: "../../other" });
    expect(logger.log).toHaveBeenCalledWith(
      expect.objectContaining({ level: "error", message: "PDF_EXPORT: Export failed" })
    );
  });
});
