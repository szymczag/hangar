/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { AddressInfo } from "node:net";
import type { Express } from "express";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/env", () => ({
  env: {
    PORT: 0,
    LIVE_BASE_PATH: "/live",
    COMPRESSION_LEVEL: 6,
    COMPRESSION_THRESHOLD: 1024,
    CORS_ALLOWED_ORIGINS: "",
  },
}));
vi.mock("@/controllers", () => ({ CONTROLLERS: [] }));
vi.mock("@/hocuspocus", () => ({ HocusPocusServerManager: { getInstance: vi.fn() } }));
vi.mock("@/redis", () => ({ redisManager: { disconnect: vi.fn() } }));

const { Server } = await import("@/server");

const SESSION = "l1v3S3ss10n";
const CSRF = "l1v3Csrf";
const BEARER = "l1v3B34r3r";

describe("Server request logging", () => {
  afterEach(() => vi.restoreAllMocks());

  it("writes the request line without the cookie, credentials or query string", async () => {
    // winston's Console transport writes to console._stdout when there is one, else through console.log.
    const written: string[] = [];
    const capture = (chunk: unknown) => {
      written.push(String(chunk));
      return true;
    };
    const consoleStdout = (console as unknown as { _stdout?: NodeJS.WriteStream })._stdout;
    if (consoleStdout) vi.spyOn(consoleStdout, "write").mockImplementation(capture);
    vi.spyOn(process.stdout, "write").mockImplementation(capture);
    vi.spyOn(console, "log").mockImplementation(capture);

    const app = (new Server() as unknown as { app: Express }).app;
    const httpServer = app.listen(0);
    await new Promise<void>((resolve) => httpServer.once("listening", () => resolve()));
    try {
      const { port } = httpServer.address() as AddressInfo;
      const response = await fetch(
        `http://127.0.0.1:${port}/live/collaboration?documentType=project_page&token=${BEARER}`,
        {
          headers: {
            Cookie: `session-id=${SESSION}; csrftoken=${CSRF}`,
            Authorization: `Bearer ${BEARER}`,
            "X-CSRFToken": CSRF,
            "User-Agent": "live-vitest",
          },
        }
      );
      await response.arrayBuffer();
      // The request is logged when the response ends; give the transport a tick to flush.
      await new Promise((resolve) => setTimeout(resolve, 20));
    } finally {
      await new Promise((resolve) => httpServer.close(resolve));
    }

    const requestLines = written.filter((line) => line.includes("/live/collaboration"));
    expect(requestLines).toHaveLength(1);
    const line = requestLines[0];
    for (const secret of [SESSION, CSRF, BEARER]) expect(line).not.toContain(secret);
    expect(line.toLowerCase()).not.toContain('"cookie"');
    expect(line.toLowerCase()).not.toContain('"authorization"');
    expect(line).toContain("live-vitest");
    expect(JSON.parse(line).message).toMatch(/^GET \/live\/collaboration 404 \d+ms$/);
  });
});
