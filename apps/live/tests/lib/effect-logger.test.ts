/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Data, Effect } from "effect";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WinstonEffectLoggerLive } from "@/lib/effect-logger";

const SECRET = "eff3ctS3cr3t";

class FetchFailed extends Data.TaggedError("FetchFailed")<{ message: string; cause?: unknown }> {}

/** Captures what the shared winston logger writes; its Console transport uses console._stdout when there is one. */
const captureStdout = () => {
  const written: string[] = [];
  const capture = (chunk: unknown) => {
    written.push(String(chunk));
    return true;
  };
  const consoleStdout = (console as unknown as { _stdout?: NodeJS.WriteStream })._stdout;
  if (consoleStdout) vi.spyOn(consoleStdout, "write").mockImplementation(capture);
  vi.spyOn(process.stdout, "write").mockImplementation(capture);
  vi.spyOn(console, "log").mockImplementation(capture);
  return () =>
    written.filter((line) => line.trim().startsWith("{")).map((line) => JSON.parse(line) as Record<string, unknown>);
};

describe("WinstonEffectLoggerLive", () => {
  afterEach(() => vi.restoreAllMocks());

  it("writes Effect log lines through the shared logger, redacted", async () => {
    const lines = captureStdout();
    const error = new FetchFailed({
      message: "Failed to fetch page content",
      cause: { config: { headers: { Cookie: `session-id=${SECRET}` } } },
    });

    await Effect.runPromise(
      Effect.gen(function* () {
        yield* Effect.logInfo("PDF_EXPORT: Starting export", { requestId: "r1", cookie: `session-id=${SECRET}` });
        yield* Effect.logError("PDF_EXPORT: Export failed", { requestId: "r1", error });
        yield* Effect.logWarning(`retrying with Cookie: session-id=${SECRET}`);
      }).pipe(Effect.provide(WinstonEffectLoggerLive))
    );

    const entries = lines();
    expect(entries.map((entry) => [entry.level, entry.message])).toEqual([
      ["info", "PDF_EXPORT: Starting export"],
      ["error", "PDF_EXPORT: Export failed"],
      ["warn", "retrying with Cookie: [REDACTED]"],
    ]);
    expect(entries[0].details).toEqual({ requestId: "r1", cookie: "[REDACTED]" });
    expect(JSON.stringify(entries[1].details)).toContain("Failed to fetch page content");
    expect(JSON.stringify(entries)).not.toContain(SECRET);
  });
});
