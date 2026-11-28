/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Writable } from "node:stream";
import type { Request, Response } from "express";
import { describe, expect, it } from "vitest";
import { transports } from "winston";
import { createLoggerMiddleware, formatRequestMessage, stripQueryString } from "./middleware";

const SESSION = "s3ss10nV4lu3";
const CSRF = "csrfV4lu3";
const BEARER = "b34r3rT0k3n";
const API_KEY = "4p1K3yV4lu3";

const logRequest = (url: string, headers: Record<string, string>): Record<string, unknown> => {
  const lines: string[] = [];
  const stream = new Writable({
    write(chunk: Buffer, _encoding, callback) {
      lines.push(chunk.toString());
      callback();
    },
  });
  const middleware = createLoggerMiddleware({ transports: [new transports.Stream({ stream })] });

  const req = { method: "GET", url, originalUrl: url, httpVersion: "1.1", headers } as unknown as Request;
  const res = {
    statusCode: 101,
    headers: { "set-cookie": `session-id=${SESSION}` },
    end: () => undefined,
  } as unknown as Response;

  middleware(req, res, () => undefined);
  res.end();

  expect(lines).toHaveLength(1);
  return { raw: lines[0], ...JSON.parse(lines[0]) };
};

describe("loggerMiddleware", () => {
  it("logs a request without its cookie, authorization, API key, CSRF header or query string", () => {
    const entry = logRequest(`/live/collaboration?documentType=project_page&token=${BEARER}`, {
      cookie: `session-id=${SESSION}; csrftoken=${CSRF}`,
      authorization: `Bearer ${BEARER}`,
      "x-api-key": API_KEY,
      "x-csrftoken": CSRF,
      "proxy-authorization": `Basic ${BEARER}`,
      "user-agent": "vitest",
    });

    const raw = entry.raw as string;
    for (const secret of [SESSION, CSRF, BEARER, API_KEY]) expect(raw).not.toContain(secret);
    for (const name of ["cookie", "authorization", "x-api-key", "x-csrftoken", "set-cookie"]) {
      expect(raw.toLowerCase()).not.toContain(`"${name}"`);
    }

    expect(entry.message).toMatch(/^GET \/live\/collaboration 101 \d+ms$/);
    const meta = entry.meta as { req: Record<string, unknown>; res: Record<string, unknown> };
    expect(meta.req).toEqual({
      method: "GET",
      url: "/live/collaboration",
      httpVersion: "1.1",
      headers: { "user-agent": "vitest" },
    });
    expect(meta.res).toEqual({ statusCode: 101 });
  });
});

describe("stripQueryString", () => {
  it("drops the query string and fragment", () => {
    expect(stripQueryString("/a/b?token=x#frag")).toBe("/a/b");
    expect(stripQueryString("/a/b#frag")).toBe("/a/b");
    expect(stripQueryString("/a/b")).toBe("/a/b");
    expect(stripQueryString(undefined)).toBe("");
  });
});

describe("formatRequestMessage", () => {
  it("percent-encodes braces so a path is never compiled as a template", () => {
    const req = { method: "GET", url: "/{{process.exit()}}", originalUrl: "/{{process.exit()}}" } as Request;
    const res = { statusCode: 404, responseTime: 2 } as unknown as Response;
    expect(formatRequestMessage(req, res)).toBe("GET /%7B%7Bprocess.exit()%7D%7D 404 2ms");
  });
});
