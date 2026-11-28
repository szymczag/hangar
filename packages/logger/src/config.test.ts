/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Writable } from "node:stream";
import { describe, expect, it } from "vitest";
import type { Logform } from "winston";
import { createLogger, format, transports } from "winston";
import { logFormat } from "./config";
import { redactFormat } from "./redact";

const SECRET = "c0nf1gS3cr3t";
const MESSAGE = Symbol.for("message");

const capture = (logFormatUnderTest: Logform.Format) => {
  const lines: string[] = [];
  const stream = new Writable({
    write(chunk: Buffer, _encoding, callback) {
      lines.push(chunk.toString());
      callback();
    },
  });
  const logger = createLogger({ format: logFormatUnderTest, transports: [new transports.Stream({ stream })] });
  return { logger, output: () => lines.join("") };
};

describe("logFormat", () => {
  it("redacts before it serialises", () => {
    const info = logFormat.transform({
      level: "info",
      message: "user fetched",
      headers: { cookie: `session-id=${SECRET}` },
    }) as Record<string | symbol, unknown>;

    expect(typeof info[MESSAGE]).toBe("string");
    expect(info[MESSAGE]).not.toContain(SECRET);
    expect(info[MESSAGE]).toContain("[REDACTED]");
  });

  it("keeps splat arguments redacted when format.splat() runs after it", () => {
    const { logger, output } = capture(format.combine(redactFormat(), format.splat(), format.json()));
    logger.info("forwarding %s", `Cookie: session-id=${SECRET}`);
    logger.info("request %o", { headers: { authorization: `Bearer ${SECRET}` } });
    logger.info("context", { token: SECRET });

    expect(output()).toContain("forwarding");
    expect(output()).not.toContain(SECRET);
  });
});
