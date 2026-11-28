/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Writable } from "node:stream";
import { describe, expect, it } from "vitest";
import { createLogger, transports } from "winston";
import { logFormat } from "./config";
import { REDACTED, redactSensitiveData, redactString } from "./redact";

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

describe("redactString", () => {
  it("redacts raw header lines, cookie pairs, query tokens and bearer tokens", () => {
    expectNoSecrets(redactString(`Cookie: ${COOKIE}\r\nAuthorization: Bearer ${BEARER}`));
    expectNoSecrets(redactString(COOKIE));
    expectNoSecrets(redactString(`/collaboration?documentType=project_page&token=${BEARER}&cookie=${SESSION}`));
    expectNoSecrets(redactString(`{"id":"u1","cookie":"${COOKIE}"}`));
  });

  it("keeps ordinary text intact", () => {
    for (const text of [
      "GET /live/collaboration?documentType=project_page&workspaceSlug=acme 101 3ms",
      "Token parsing failed, using request headers",
    ]) {
      expect(redactString(text)).toBe(text);
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
