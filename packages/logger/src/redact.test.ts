/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Writable } from "node:stream";
import { describe, expect, it } from "vitest";
import { createLogger, transports } from "winston";
import { logFormat } from "./config";
import { MAX_NODES, REDACTED, redactSensitiveData, redactString } from "./redact";

const SESSION = "s3ss10nV4lu3";
const CSRF = "csrfV4lu3";
const BEARER = "b34r3rT0k3n";
const COOKIE = `session-id=${SESSION}; csrftoken=${CSRF}`;

const captureLogger = () => {
  const lines: string[] = [];
  const stream = new Writable({
    write(chunk: Buffer, _encoding, callback) {
      lines.push(chunk.toString());
      callback();
    },
  });
  const logger = createLogger({ level: "debug", format: logFormat, transports: [new transports.Stream({ stream })] });
  return { logger, output: () => lines.join("") };
};

const expectNoSecrets = (text: string) => {
  expect(text).not.toContain(SESSION);
  expect(text).not.toContain(CSRF);
  expect(text).not.toContain(BEARER);
};

/** An error shaped like the one axios rejects with: the request config and the Node request both carry the cookie. */
const axiosLikeError = () => {
  const error = new Error("Request failed with status code 403") as Error & Record<string, unknown>;
  const config = {
    method: "get",
    url: "/api/users/me/",
    headers: { Accept: "application/json", Cookie: COOKIE, Authorization: `Bearer ${BEARER}` },
  };
  const request: Record<string, unknown> = {
    _header: `GET /api/users/me/ HTTP/1.1\r\nAccept: application/json\r\nCookie: ${COOKIE}\r\nAuthorization: Bearer ${BEARER}\r\nHost: api\r\n\r\n`,
  };
  request.self = request;
  Object.assign(error, {
    isAxiosError: true,
    code: "ERR_BAD_REQUEST",
    config,
    request,
    response: { status: 403, headers: { "set-cookie": [`session-id=${SESSION}; Path=/`] }, config },
  });
  return error;
};

const SECRET = "zq9Secr3t";

describe("redactString", () => {
  it("redacts raw header lines, cookie pairs, query tokens and bearer tokens", () => {
    expectNoSecrets(redactString(`Cookie: ${COOKIE}\r\nAuthorization: Bearer ${BEARER}`));
    expectNoSecrets(redactString(COOKIE));
    expectNoSecrets(redactString(`/collaboration?documentType=project_page&token=${BEARER}&cookie=${SESSION}`));
    expectNoSecrets(redactString(`{"id":"u1","cookie":"${COOKIE}"}`));
  });

  it.each([
    ["a header in the middle of a line", `sent Cookie: renamed-session=${SECRET}; theme=dark to the API`],
    [
      "JSON-escaped raw header text",
      `GET / HTTP/1.1\\r\\nCookie: a=${SECRET}\\r\\nX-Api-Key: ${SECRET}\\r\\nHost: api`,
    ],
    [
      "util.inspect quoted keys",
      `{ 'x-api-key': '${SECRET}', 'live-server-secret-key': '${SECRET}', 'cookie': '${SECRET}' }`,
    ],
    ["a quoted token key", `{'token': '${SECRET}'}`],
    ["a bare util.inspect key", `{ token: '${SECRET}', name: 'n' }`],
    ["a JSON key", `{"x-csrftoken":"${SECRET}"}`],
    ["a lower-case bearer scheme", `bearer ${SECRET}`],
    ["a lower-case basic scheme", `auth basic ${SECRET}`],
    ["a Token scheme", `Authorization header was Token ${SECRET}0123456789abcdef`],
    ["an authorization assignment with a scheme", `authorization=bearer ${SECRET}`],
    ["a renamed session cookie after cookie=", `cookie=custom-session=${SECRET}; theme=dark`],
    ["URL userinfo", `redis://:${SECRET}@redis:6379/0`],
    ["URL user and password", `https://user:${SECRET}@example.com/path`],
    ["a percent-encoded parameter name", `/live/x?%74oken=${SECRET}&a=1`],
    [
      "a presigned signature and credential",
      `https://s3/b/k?X-Amz-Credential=${SECRET}&X-Amz-Signature=${SECRET}&X-Amz-Date=1`,
    ],
  ])("redacts %s", (_label, input) => {
    expect(redactString(input)).not.toContain(SECRET);
  });

  it("keeps ordinary text intact", () => {
    for (const text of [
      "GET /live/collaboration?documentType=project_page&workspaceSlug=acme 101 3ms",
      "Token parsing failed, using request headers",
      "https://example.com/path?X-Amz-Date=20260101",
      'Hello "name": "bob"',
    ]) {
      expect(redactString(text)).toBe(text);
    }
  });

  it("stays linear on 200 KB adversarial inputs", () => {
    const size = 200_000;
    const inputs = [
      "a".repeat(size),
      `\n${" ".repeat(size)}`,
      '"a":'.repeat(size / 4),
      `"a":"${"x".repeat(size)}`,
      "'a':".repeat(size / 4),
      "a: ".repeat(size / 3),
      `Bearer ${" ".repeat(size)}`,
      `Cookie:${" \t".repeat(size / 2)}`,
      `a://${"x".repeat(size)}`,
      "a://b".repeat(size / 5),
      " a".repeat(size / 2),
      `token ${"a".repeat(15)}${" ".repeat(size)}`,
      "%".repeat(size),
      '"'.repeat(size),
      "a:`".repeat(size / 3),
      "'a':\"".repeat(size / 5),
      "\\r\\n".repeat(size / 4),
    ];
    for (const input of inputs) {
      const start = performance.now();
      redactString(input);
      expect(performance.now() - start).toBeLessThan(500);
    }
  });
});

describe("redactSensitiveData", () => {
  it("replaces values under credential keys at any depth without touching the input", () => {
    const input = { req: { headers: { cookie: COOKIE, "X-CSRFToken": CSRF, "user-agent": "vitest" } } };
    const output = redactSensitiveData(input);

    expect(output.req.headers.cookie).toBe(REDACTED);
    expect(output.req.headers["X-CSRFToken"]).toBe(REDACTED);
    expect(output.req.headers["user-agent"]).toBe("vitest");
    expect(input.req.headers.cookie).toBe(COOKIE);
  });

  it("replaces binary data with its size", () => {
    const header = Buffer.from(`Cookie: ${COOKIE}`);
    const output = redactSensitiveData({ body: header, bytes: new Uint8Array(header), raw: header.buffer });

    expect(output.body).toBe(`[Buffer ${header.length} bytes]`);
    expect(output.bytes).toBe(`[Uint8Array ${header.length} bytes]`);
    expect(String(output.raw)).toMatch(/^\[ArrayBuffer \d+ bytes\]$/);
    expectNoSecrets(JSON.stringify(output));
  });

  it("redacts the value after a sensitive name in a flat header list", () => {
    const rawHeaders = ["Host", "api", "Cookie", COOKIE, "X-CSRFToken", CSRF, "User-Agent", "vitest"];
    expect(redactSensitiveData(rawHeaders)).toEqual([
      "Host",
      "api",
      "Cookie",
      REDACTED,
      "X-CSRFToken",
      REDACTED,
      "User-Agent",
      "vitest",
    ]);
  });

  it("walks a shared object once and keeps cycles and node counts bounded", () => {
    // A 4-way DAG ten levels deep has a million paths but only eleven distinct objects.
    let node: Record<string, unknown> = { cookie: COOKIE };
    for (let level = 0; level < 10; level += 1) node = { a: node, b: node, c: node, d: node };
    const start = performance.now();
    const output = redactSensitiveData(node);
    expect(performance.now() - start).toBeLessThan(200);
    expectNoSecrets(JSON.stringify(output).slice(0, 10_000));

    const cyclic: Record<string, unknown> = { token: BEARER };
    cyclic.self = cyclic;
    expect(redactSensitiveData(cyclic)).toEqual({ token: REDACTED, self: "[Circular]" });

    const wide = Array.from({ length: MAX_NODES * 2 }, (_, index) => ({ index }));
    const truncated = redactSensitiveData(wide) as unknown[];
    expect(truncated.filter((item) => item === "[Truncated]").length).toBeGreaterThan(0);
  });

  it("redacts an axios-like error and leaves the error usable", () => {
    const error = axiosLikeError();
    const output = redactSensitiveData({ error }) as { error: Record<string, unknown> };

    expectNoSecrets(JSON.stringify(output));
    expect(output.error.message).toBe("Request failed with status code 403");
    expect((error.config as { headers: { Cookie: string } }).headers.Cookie).toBe(COOKIE);
  });
});

describe("logger", () => {
  it("writes an axios-like error with its message but without the cookie or bearer token", () => {
    const { logger, output } = captureLogger();
    logger.error("Failed to fetch current user", axiosLikeError());

    const text = output();
    expectNoSecrets(text);
    expect(text).toContain("Failed to fetch current user");
    expect(text).toContain("ERR_BAD_REQUEST");
    expect(text).toContain(REDACTED);
  });

  it("redacts credentials in metadata and in the message", () => {
    const { logger, output } = captureLogger();
    logger.info(`token=${BEARER}`, { headers: { Cookie: COOKIE }, context: { authorization: `Bearer ${BEARER}` } });

    expectNoSecrets(output());
  });
});
